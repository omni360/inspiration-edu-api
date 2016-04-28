from django.db import models, transaction, OperationalError, IntegrityError
from django.core.exceptions import ValidationError

from utils_app.models import DeleteStatusModel


class OrderedObjectInContainerSettings:
    '''Object class to hold ordered settings'''
    order_field = None
    ordered_key_field = None
    container_key_field = None


class OrderedObjectInContainer(object):
    '''
    This mixin for a django model takes care of ordering objects in containers.
    A container model can connect many objects to itself. Each object is ordered in a unique position under the
    container. The order field is zero-based, and this mixin makes sure that order_field has a complete order set
    from 0 to count-1, keeping the order_field valid as array indices.

    If container_key_field is None (not ordered under containers), the order field will be unique for all the objects
    of self model's type.
    If ordered_key_field is None, then use the self object PK as the ordered_key_field, ordering self.

    In your model you may define a container field, and define an ordered model field in a through model.
    To make it clear:
        Model contains: container_key_field, ordered_key_field, order_field.
    You must take care to define the ordered field in your model, as:
        order = models.IntegerField(db_index=True, null=False)
    You must follow these 2 constraints (on your model, use unique_together in Meta class):
        1. Unique (container_key_field, ordered_key_field).
        2. Unique (container_key_field, order_field).
    If not container_key_field, then both of the unique constraints will contain a single field:
        1. Unique (ordered_key_field).
        2. Unique (order_field).
    If no ordered_key_field, then the first unique constraint is already satisfied as it is actually the object PK.

    It might be better to declare ordering on the model using:
        ordering = (container_key_field, order_field)

    In your model create a meta class OrderedObjectInContainerSettings, and define following attributes:
        1. order_field - The "order" field name of your model.
        2. ordered_key_field - The ordered key field in your model.
        3. container_key_field - The container key field in your model.
    '''
    # def __new__(cls, *args, **kwargs):
    def __init__(self, *args, **kwargs):
        super(OrderedObjectInContainer, self).__init__(*args, **kwargs)

        order_settings = getattr(self, 'OrderedObjectInContainerSettings', object())
        self._order_settings = OrderedObjectInContainerSettings()
        self._order_settings.order_field = getattr(order_settings, 'order_field', 'order')
        self._order_settings.ordered_key_field = getattr(order_settings ,'ordered_key_field', None)
        self._order_settings.container_key_field = getattr(order_settings, 'container_key_field', None)
        if not self._order_settings.ordered_key_field:
            self._order_settings.ordered_key_field = 'pk'  #defaults to self (using PK)

    def save(self, *args, **kwargs):
        '''
        Saves the ordered object with the correct order position in the container.
        This operation uses transaction with row-locks for update, for concurrent handling.
        '''

        # Assumptions:
        # 1: unique (container_key_field, ordered_key_field).
        # 2: unique (container_key_field, order_field)

        #if object is deleted, then skip the order fix:
        if isinstance(self, DeleteStatusModel) and self.is_deleted:
            return super(OrderedObjectInContainer, self).save(*args, **kwargs)

        #make queryset of the entries in the container:
        qs_container_ordered_objects = self._meta.model.objects.all()
        if self._order_settings.container_key_field:
            qs_container_ordered_objects = qs_container_ordered_objects.filter(
                **{self._order_settings.container_key_field: getattr(self, self._order_settings.container_key_field)}
            )

        #helper function to get the ordered object queryset:
        def helper_get_ordered_object_qs():
            qs_ordered_object = qs_container_ordered_objects.filter(
                **{self._order_settings.ordered_key_field: getattr(self, self._order_settings.ordered_key_field)}
            )
            return qs_ordered_object
        #helper function to get the current order of an existing object (when not created):
        def helper_get_cur_order():
            cur_order = helper_get_ordered_object_qs().values_list(self._order_settings.order_field)
            cur_order = cur_order[0][0] if cur_order else None
            return cur_order

        #helper function to save object in the right order:
        def helper_save_object_ordered(locked=False):
            #current amount of objects in container
            num_objs_in_container = qs_container_ordered_objects.count()

            #get current order:
            cur_order = helper_get_cur_order()

            #actual new_order to save:
            new_order = getattr(self, self._order_settings.order_field, None)

            #set flag if new_order need to be last:
            new_order_last = False
            if new_order is None:
                new_order_last = True
                #set new_order to currently next last position (if moved from cur_order, then put it instead of the current last):
                new_order = num_objs_in_container
                if cur_order is not None:
                    new_order -= 1

            #if order was chagned:
            if cur_order is None or cur_order != new_order:

                #if not locked, then first try to lock:
                if not locked:
                    # IMPORTANT NOTE:
                    #       [ See: http://www.postgresql.org/message-id/flat/freemail.20070030161126.43285@fm10.freemail.hu ]
                    #       When using a transaction with 'read commit' isolation level (default for Django-Postgres),
                    #       any row updated inside a transaction is automatically locked for updated.
                    #       Lock is released when transaction is either committed or rolled back.
                    #       When you lock with .select_for_update() [SELECT ... FOR UPDATE], firstly database selects the rows,
                    #       and then tries to lock EACH row in the order returned. When getting to a row that is already locked
                    #       by another transaction the query is pending till the row-lock is released and can be acquired again.
                    #       Important, if you do not use select for update with any order, and got some queries pending
                    #       in multi-processing, every select for update query is pending to lock an arbitrary row in random
                    #       order, which can cause deadlock!
                    #       [For example: thread-1 is pending to lock rows 5,2,4 and thread-2 is pending to lock rows 4,5,2.
                    #       When the row-locks are released, thread-1 locks row 5 and 2, thread-2 locks row 4 and is pending
                    #       to lock row 5 blocked by row-lock of thread-1! And thread-1 is pending to lock row 2 that is
                    #       blocked by thread-2! thread-1 and thread-2 are pending for each other -> DeadLock!].
                    #       To avoid deadlocks, always select for update in determined order.
                    #       Moreover, it is still possible to face a deadlock. For example, when thread-1 and thread-2 are
                    #       pending to lock rows 3,2,1. The current thread-0 makes a new row 4 and commits. Thread-1 locks 3,2,1
                    #       while thread-2 is pending for 3,2,1. Now another thread-3 enters and tries to lock 4,3,2,1. If
                    #       current running thread-1 modifies also row 4, it will fail since row 4 is locked by thread-3 that
                    #       also pending to lock rows blocked by thread-1 -> DeadLock!
                    #       For the last case, OperationalError exception is raised.
                    #       IntegrityError exception might be raised when a locked transaction is trying to insert in the
                    #       same place as the previous blocking transaction did, and the new row was not locked.
                    #       In addition, if still a transaction fails, it will be retried up to limited times (defined as 5).
                    #lock for update all rows referencing the container that are going to be updated:
                    #(note that cur_order can be changed with multi-processing, so do not rely on it for locking).
                    list(
                        qs_container_ordered_objects.values(
                            self._order_settings.order_field
                        ).order_by(
                            '-'+self._order_settings.order_field
                        ).select_for_update()
                    )

                    #after lock, save the object ordered:
                    helper_save_object_ordered(True)
                    return

                #we first make room for the target order, then move up to fill the cur_order that was moved:
                if cur_order is not None and cur_order < new_order:
                    new_order += 1

                #move down all entries with order greater than equal to new_order:
                #Note: since constraint is not deferred, we have to move all to safe range and then back to their
                #      desired place. (otherwise, updating each row will overlap another and raise unique key error).
                qs_container_ordered_objects.filter(
                    **{self._order_settings.order_field+'__gte': new_order}
                ).update(
                    **{self._order_settings.order_field: models.F(self._order_settings.order_field) + num_objs_in_container + 1000}
                )
                qs_container_ordered_objects.filter(
                    **{self._order_settings.order_field+'__gte': num_objs_in_container + 1000}
                ).update(
                    **{self._order_settings.order_field: models.F(self._order_settings.order_field) - num_objs_in_container - 999}
                )

                #since cur_order can be changed in multi-processing, read the cur_order again:
                if cur_order is not None:
                    cur_order = helper_get_cur_order()

                #set the new_order
                setattr(self, self._order_settings.order_field, new_order)

                #save the object:
                super(OrderedObjectInContainer, self).save(*args, **kwargs)

                #if cur_order, move up all entries with order greater than cur_order:
                if cur_order is not None:
                    #Note: since constraint is not deferred, we have to move all to safe range and then back to their
                    #      desired place. (otherwise, updating each row will overlap another and raise unique key error).
                    qs_container_ordered_objects.filter(
                        **{self._order_settings.order_field+'__gte': cur_order}
                    ).update(
                        **{self._order_settings.order_field: models.F(self._order_settings.order_field) + num_objs_in_container + 1000}
                    )
                    qs_container_ordered_objects.filter(
                        **{self._order_settings.order_field+'__gte': num_objs_in_container + 1000}
                    ).update(
                        **{self._order_settings.order_field: models.F(self._order_settings.order_field) - num_objs_in_container - 1001}
                    )

                    #set the new_order of the object (no need to save, since the previous update did the change in db):
                    if cur_order < new_order:
                        new_order -= 1
                        setattr(self, self._order_settings.order_field, new_order)

                #correct the value of new_order in case it is greater than the entries ordered:
                max_order = qs_container_ordered_objects.count() - 1
                if new_order > max_order:
                    new_order = max_order
                    helper_get_ordered_object_qs().update(
                        **{self._order_settings.order_field: new_order}
                    )
                    setattr(self, self._order_settings.order_field, new_order)

            #else, if order was not changed:
            else:
                #save the object:
                super(OrderedObjectInContainer, self).save(*args, **kwargs)

        #do the transaction and retry on OperationalError or IntegrityError failures (limited to 5 retries):
        retries_limit = 5
        for n_retry in xrange(0, retries_limit):
            try:
                #do transaction:
                with transaction.atomic():
                    helper_save_object_ordered()
            #if failed to make the transaction, loop again and retry:
            except (OperationalError, IntegrityError):
                #re-raise the error if max retries is exceeding:
                if n_retry == retries_limit-1:
                    raise
            #if committed successfully, then break the retries loop:
            else:
                break

    def delete(self, *args, **kwargs):
        '''
        Deleted the ordered object from the container and corrects the order positions of the objects left.
        This operation uses transaction with row-locks for update, for concurrent handling.
        '''

        #if object is deleted, then skip the order fix:
        if isinstance(self, DeleteStatusModel) and self.is_deleted:
            return super(OrderedObjectInContainer, self).delete(*args, **kwargs)

        #make queryset of the entries in the container:
        qs_container_ordered_objects = self._meta.model.objects.all()
        if self._order_settings.container_key_field:
            qs_container_ordered_objects = qs_container_ordered_objects.filter(
                **{self._order_settings.container_key_field: getattr(self, self._order_settings.container_key_field)}
            )

        #helper function to get the ordered object queryset:
        def helper_get_ordered_object_qs():
            qs_ordered_object = qs_container_ordered_objects.filter(
                **{self._order_settings.ordered_key_field: getattr(self, self._order_settings.ordered_key_field)}
            )
            return qs_ordered_object
        #helper function to get the current order of an existing object (when not created):
        def helper_get_cur_order():
            cur_order = helper_get_ordered_object_qs().values_list(self._order_settings.order_field)
            cur_order = cur_order[0][0] if cur_order else None
            return cur_order

        #helper function to delete object and move up all objects below it:
        def helper_save_object_ordered():
            #current amount of objects in container
            num_objs_in_container = qs_container_ordered_objects.count()

            #lock for update all rows referencing the container that are going to be updated:
            #(note that cur_order can be changed with multi-processing, so do not rely on it for locking).
            list(
                qs_container_ordered_objects.values(
                    self._order_settings.order_field
                ).order_by(
                    '-'+self._order_settings.order_field
                ).select_for_update()
            )

            #get current order:
            cur_order = helper_get_cur_order()

            #delete the object:
            super(OrderedObjectInContainer, self).delete(*args, **kwargs)

            #move up all entries with order greater than cur_order:
            #Note: since constraint is not deferred, we have to move all to safe range and then back to their
            #      desired place. (otherwise, updating each row will overlap another and raise unique key error).
            qs_container_ordered_objects.filter(
                **{self._order_settings.order_field+'__gte': cur_order}
            ).update(
                **{self._order_settings.order_field: models.F(self._order_settings.order_field) + num_objs_in_container + 1000}
            )
            qs_container_ordered_objects.filter(
                **{self._order_settings.order_field+'__gte': num_objs_in_container + 1000}
            ).update(
                **{self._order_settings.order_field: models.F(self._order_settings.order_field) - num_objs_in_container - 1001}
            )  #decrease order by 1 for all above

        #do the transaction and retry on OperationalError or IntegrityError failures (limited to 5 retries):
        obj_pk = self.pk
        retries_limit = 5
        for n_retry in xrange(0, retries_limit):
            try:
                #do transaction:
                with transaction.atomic():
                    helper_save_object_ordered()
            #if failed to make the transaction, loop again and retry:
            except (OperationalError, IntegrityError):
                self.pk = obj_pk  #restore pk since .delete() removes it from the object
                #re-raise the error if max retries is exceeding:
                if n_retry == retries_limit-1:
                    raise
            #if committed successfully, then break the retries loop:
            else:
                break


    def save_container_list_order(self, new_ordered_keys_list, container_key=None, save_kwargs={}):
        '''
        Shortcut method to set ordered list for all objects of a container (in case object is not ordered under any
        container, container_key argument is ignored).
        Input new_ordered_keys_list must contain all the ordered objects keys in the container. It is not allowed to
        add/remove any ordered objects with this method, but only order them all.
        You can use save_kwargs argument that will be passed to any ordered object .save() method.
        This method is global, that means the ordered object does not have to be saved in order to use this function,
        so it is possible to init an empty ordered object and call this function.
        '''

        #make queryset of ordered objects in the container (in case container_key_field is set):
        qs_container_ordered_objects = self._meta.model.objects.all().order_by(self._order_settings.order_field)
        if self._order_settings.container_key_field:
            if container_key is None:
                raise ValidationError('Container key must be supplied')
            qs_container_ordered_objects = qs_container_ordered_objects.filter(
                **{self._order_settings.container_key_field: container_key}
            )

        #get current ordered keys list:
        cur_ordered_keys_list = list(
            qs_container_ordered_objects.values_list(self._order_settings.ordered_key_field, flat=True)
        )  #force invoke

        #validate that all keys exist in the new list:
        if set(new_ordered_keys_list) != set(cur_ordered_keys_list):
            raise ValidationError('Can only change order, but not add/remove objects')

        #go over the list and optimize order transfers:
        #TODO: Optimize a better algorithm to produce the transfers dict.
        transfers = []
        for order, cur_ordered_key in enumerate(cur_ordered_keys_list):
            if cur_ordered_key != new_ordered_keys_list[order]:
                transfers.append((cur_ordered_key, new_ordered_keys_list.index(cur_ordered_key),))
        #NOTE: Consider to use transaction for ordering the list:
        for transfer_ordered_key, transfer_order in transfers:
            #get the ordered object [Note: (container_key_field, ordered_key_field) is unique]:
            ordered_object = qs_container_ordered_objects.get(
                **{self._order_settings.ordered_key_field: transfer_ordered_key}
            )
            setattr(ordered_object, self._order_settings.order_field, transfer_order)
            ordered_object.save(**save_kwargs)  #save the object with the new order without changing its updated field
