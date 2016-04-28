'use strict';

angular.module('adminApp')
    .controller('ProjectAdminCtrl', [
        '$scope',
        'filePickerParams',
        function ($scope, filePickerParams) {
            $scope.bannerImgUrl = '';
            $scope.cardImgUrl = '';

            $scope.projectBannerFilePickerOptions = {
                allowedMimes: ['image/*'],
                excludedMimes: ['image/gif'],
                crop: true,
                maxFilenameLength: 150
            };
            $scope.projectBannerImageAreaSelectOptions = {
                aspectRatio: '1920:350',
                fadeSpeed: 500,
                disableCancelSelection: true,  //disable cancel selection
                minWidth: 1920,
                minHeight: 350,
                x1: 0,
                y1: 0,
                x2: 1920,
                y2: 350
            };
            $scope.projectBannerImageOptions = {
                minWidth: 1920,
                minHeight: 350
            };
            //project cardImage options:
            $scope.projectCardImageFilePickerOptions = {
                allowedMimes: ['image/*'],
                excludedMimes: ['image/gif'],
                crop: true,
                maxFilenameLength: 150
            };
            $scope.projectCardImageAreaSelectOptions = {
                aspectRatio: '4:3',
                fadeSpeed: 500,
                disableCancelSelection: true,  //disable cancel selection
                minWidth: 340,
                minHeight: 255,
                x1: 0,
                y1: 0,
                x2: 340,
                y2: 255
            };
            $scope.projectCardImageOptions = {
                minWidth: 340,
                minHeight: 255
            };

            filePickerParams.setCredentials('ignite-site-dev/uploads', 'AKIAIVA4IEDJLZ7O7OZQ', 'w24RyD+c2RNd9D6+90ypaNpxbW/0mJ+uJR1vSBz2');

            $scope.$watch('bannerImgUrl', function() {
                if ($scope.bannerImgUrl !== '') {
                    var inputElement = $('#bannerImageDiv').find('.vURLField');
                    inputElement[0].value = $scope.bannerImgUrl;
                }
            });

            $scope.$watch('cardImgUrl', function() {
                if ($scope.cardImgUrl !== '') {
                    var inputElement = $('#cardImageDiv').find('.vURLField');
                    inputElement[0].value = $scope.cardImgUrl;
                }
            });
        }]);