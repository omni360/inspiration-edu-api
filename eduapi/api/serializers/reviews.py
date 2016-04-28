from django.db import IntegrityError, transaction
from django.contrib.contenttypes.models import ContentType

from rest_framework import serializers

from .fields import (
    ReviewHyperlinkedIdentityField,
    ReviewedItemHyperlinkedIdentityField,
)
from .users import (
    UserSerializer,
)

from ..models import (
    Review,
)


class ReviewedItem(serializers.ModelSerializer):
    '''
    A Review's content_object serializer.

    Serializes the content_object of a Review instance. That is the item that
    the review was written about.

    E.g. - If a review was written about a project with ID 74 
    (/projects/74/reviews/:id/) then this serializer serializes project 74.
    '''

    id = serializers.ReadOnlyField(source='object_id')
    type = serializers.ReadOnlyField(source='content_type.model')
    self = ReviewedItemHyperlinkedIdentityField()
    title = serializers.ReadOnlyField(source='content_object.title')

    class Meta:
        model = Review
        fields = (
            'id',
            'self',
            'type',
            'title',
        )

class ReviewSerializer(serializers.ModelSerializer):
    """
    Serializes a generic review
    """

    author = UserSerializer(source='owner', read_only=True)
    self = ReviewHyperlinkedIdentityField()

    reviewedItem = ReviewedItem(source='*', read_only=True)
    added = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Review
        fields = (
            'id',
            'self',
            'text',
            'rating',
            'added',
            'author',
            'reviewedItem',
        )

    def create(self, validated_data):
        ''' Associate the item with the relevant object before it's saved '''

        try:
            # transcation.atomic() is necessary because otherwise Django won't
            # be able to run additional DB queries if an IntegrityError occurs.
            with transaction.atomic():
                return super(ReviewSerializer, self).create(validated_data)
        except IntegrityError, e:
            # Failed because of integrity error, check if a review by the user
            # for the same object exists.
            content_object = validated_data['content_object']
            reviews = Review.objects.active_and_deleted().filter(
                owner=validated_data['owner'],
                content_type_id=ContentType.objects.get_for_model(content_object).id,
                object_id=content_object.id,
            )

            if reviews.count():
                # If so, instead of creating a new review try to override 
                # the previous one.
                reviews.delete(really_delete=True)
                return super(ReviewSerializer, self).create(validated_data)
            else:
                raise e
