from django.conf import settings

from utils_app.spark_drive import SparkDriveApi

from .models import IgniteUser


class SparkDriveOperations(SparkDriveApi):
    '''
    SparkDriveApi with extensions for Ignite.
    '''

    @staticmethod
    def _fix_default_avatar(path):
        """Replaces default avatar with avatar from settings or HTTPS version.

        The default avatar is using HTTP. So at the very least we want to use
        HTTPS instead. But if there's an avatar in the settings, it'll override
        the default one.
        """

        http = 'http://'
        lpath = path.lower()

        if lpath.startswith(http) and lpath.endswith('member/default_avatar.png'):
            return settings.DEFAULT_USER_AVATAR or ('https://' + path[len(http):])
        else:
            return path

    def _create_or_update_user_v1(self, user_dict):
        '''
        Creates or updates the Ignite user from the member that is logged in into Spark Drive.
        Using Spark Drive V1.

        :return: tuple (user, created).
        '''
        # get member age:
        max_age = IgniteUser.COPPA_CHILD_THRESHOLD
        try:
            age = int(user_dict.get('AGE', max_age))
            if age == -1:
                age = max_age
        except ValueError:
            age = max_age

        # Map user data to model data
        user_model_data = {
            'member_id':    user_dict['MEMBERID'],
            'email':        user_dict['EMAIL'],
            'name':         user_dict['MEMBERNAME'],
            'short_name':   user_dict['MEMBERINITIALNAME'],
            'is_child':     age < max_age,
            'avatar':       self._fix_default_avatar(user_dict['PROFILE']['AVATARPATH']),
            'oxygen_id':    user_dict['OXYGEN_ID'],
        }
        if 'PARENT_EMAIL' in user_dict:
            user_model_data['PARENT_EMAIL'] = user_dict['PARENT_EMAIL']

        # Credentials are valid, try get the user, or create fresh user
        created = False
        try:
            user = IgniteUser.objects.get(member_id=user_dict['id'])
        except IgniteUser.DoesNotExist:
            created = True
            user = IgniteUser()

        # Update the ignite user model
        need_save = created
        if not need_save:
            for k,v in user_model_data.items():
                if getattr(user, k, None) != v:
                    setattr(user, k, v)
                    need_save = True

        # Save only if needed
        if need_save:
            user.save()

        return user, created

    def _create_or_update_user_v2(self, user_dict):
        '''
        Creates or updates the Ignite user from the member that is logged in into Spark Drive.
        Using Spark Drive V2.

        :return: tuple (user, created).
        '''
        # get member age:
        max_age = IgniteUser.COPPA_CHILD_THRESHOLD
        try:
            age = int(user_dict.get('age', max_age))
            if age == -1:
                age = max_age
        except ValueError:
            age = max_age

        # Map user data to model data
        user_model_data = {
            'member_id':    user_dict['id'],
            'email':        user_dict['email'],
            'name':         user_dict['name'],
            'short_name':   user_dict['first_name'],
            'is_child':     age < max_age,
            'avatar':       self._fix_default_avatar(user_dict['profile']['avatar_path']),
            'oxygen_id':    user_dict['oxygen_id'],
        }
        if 'parent_email' in user_dict:
            user_model_data['parent_email'] = user_dict['parent_email']

        # Credentials are valid, try get the user, or create fresh user
        created = False
        try:
            user = IgniteUser.objects.get(member_id=user_dict['id'])
        except IgniteUser.DoesNotExist:
            created = True
            user = IgniteUser()

        # Update the ignite user model
        need_save = False
        for k,v in user_model_data.items():
            if getattr(user, k, None) != v:
                setattr(user, k, v)
                need_save = True

        # Save only if needed
        if need_save:
            user.save()

        return user, created

    def get_logged_in_ignite_user(self):
        '''
        Creates or updates the Ignite user from the member that is logged in into Spark Drive.

        :return: tuple (user, created).
        '''
        return self.get_logged_in_ignite_user_v2()

    def get_logged_in_ignite_user_v1(self):
        #get member data (using SparkDrive V1):
        user_dict = self.member_data()

        #create or update the user:
        return self._create_or_update_user_v1(user_dict)

    def get_logged_in_ignite_user_v2(self):
        #get member data (using SparkDrive V2):
        user_dict = self.member_data_v2()

        #create or update the user:
        return self._create_or_update_user_v2(user_dict)

    def sync_user(self, user):
        '''

        :param user: the ignite user to synchronize from Spark Drive.
        :return: None.
        '''
        #read spark drive member data from spark drive and update user in our system:
        sparkdrive_member = self.member_data_v2(user.member_id)

        #update ignite user object:
        sparkdrive_member_profile = sparkdrive_member.get('profile', {})
        user.email = sparkdrive_member.get('email', user.email)
        user.name = sparkdrive_member.get('name', user.name)
        user.avatar = sparkdrive_member_profile.get('avatar_path', user.avatar)

        #save the user:
        user.save()

    def update_user(self, user, data):
        '''
        Updates the ignite user via Spark Drive.

        :param user: the ignite user to update
        :param data: data to update (using spark drive api v2).
        :return: None.
        '''
        #check arguments:
        if not isinstance(user, IgniteUser):
            raise self.SparkDriveApiError('User must be Ignite User.')
        if not user.member_id:
            raise self.SparkDriveApiError('User has no SparkDrive member ID.')
        data = data or {}

        #use only changed data, avoid call to SparkDrive in case data was not changed:
        data = {k:v for k,v in data.items() if getattr(user, k) != v}

        #if avatar is updated, then first process it:
        avatar = data.pop('avatar', None)
        if avatar:
            #if avatar is numeric, assume that is the correct spark file id:
            if unicode(avatar).isnumeric():
                data['avatar'] = avatar
            #else, assume it is url of the file to retrieve:
            else:
                #Note: uploading any file url, even if it is not changed from current user object, will result in a new file uploaded to SparkDrive.
                try:
                    sparkdrive_avatar_file = self.upload_file_from_url(avatar, public=True)
                except self.SparkDriveApiError:
                    raise  #if avatar failed to upload, then raise error (note that avatar field is already omitted from data to update)
                else:
                    #if uploaded, then set avatar attribute to update to the file id uploaded:
                    sparkdrive_avatar_file_id = sparkdrive_avatar_file.get('file_id', None)
                    if sparkdrive_avatar_file_id:
                        data['avatar'] = sparkdrive_avatar_file_id

        #if nothing to update:
        if not data:
            return

        #update spark drive member data:
        if self.update_member(data, user.member_id):
            #synchronize user data from spark drive:
            self.sync_user(user)
