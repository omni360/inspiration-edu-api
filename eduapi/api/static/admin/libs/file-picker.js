'use strict';
/*global $:false */
/*global AWS:false */

var filePickerApp = angular.module('filePickerApp', []);

// File picker browse directive
angular.module('filePickerApp').directive('fileBrowse', ['$compile', 'filePickerCommon', function($compile, filePickerCommon) {
	return {
		restrict: 'A',
		link: function(scope, elem) {
			elem.bind('change', function(event){
				// If user chose a file and file upload is not in progress (can happen when user opens the file browse window and then drags a file to the file-drop zone)
				if (event.target.files.length && !filePickerCommon.getUploadInProgressStatus()) {
					scope.initUpload();

					scope.setFilesArray(event.target.files);

                    var areFilesValid = scope.validateFiles();

                    if (areFilesValid) {
                        // Show progress for each file selected
                        scope.clearDropZone();
                        angular.forEach(scope.filesArray, function (file, idx) {
                            // Show file upload progress inside the drop zone
                            var progressBar = angular.element('<upload-progress show-file-details="true" file-index="' + idx + '"></upload-progress>');
                            $compile(progressBar)(scope);
                            scope.addUploadProgressToDropZone(progressBar);

                            // Sum files size
                            scope.totalSize += file.size;
                        });

                        // Disable file browsing button
                        $('.btn-file').addClass('disabled');

                        scope.$apply();

                        scope.uploadAll();
                    } else {
				        scope.setDropZoneMsg(scope.fileValidationError , true);
                    }
				}
			});
		}
	};
}]);

// File drop zone directive
angular.module('filePickerApp').directive('fileDrop', ['$compile', 'filePickerCommon', function($compile, filePickerCommon) {
	return {
		restrict : 'A',
		link: function (scope, elem) {
			elem.bind('dragover', function(e) {
				e.preventDefault();
			});

			elem.bind('dragenter', function(e) {
                if (!filePickerCommon.getUploadInProgressStatus()) {
                    // Make sure only files are being dragged in
                    var isAllFiles = true;
                    for (var i = 0; i < e.originalEvent.dataTransfer.types.length; i++) {
                        if (e.originalEvent.dataTransfer.types[i] !== 'Files') {
                            isAllFiles = false;
                        }
                    }

                    if (isAllFiles) {
                        scope.clearDropZone();
                        angular.element(e.target).addClass('drag-active');
                        angular.element(e.target).html('Drop to upload');
                    }
                }
			});

			elem.bind('dragleave', function(e) {
                if (!filePickerCommon.getUploadInProgressStatus()) {
                    angular.element(e.target).removeClass('drag-active');
                    angular.element(e.target).html('Drag file here');
                }
			});

			elem.bind('drop', function(e) {
				e.preventDefault();
				e.stopPropagation();

                if (e.originalEvent.dataTransfer.files.length && !filePickerCommon.getUploadInProgressStatus()) {
                    scope.initUpload();

                    // Check if multiple file selection occurred and is not allowed
                    if ((e.originalEvent.dataTransfer.files.length > 1) && (!scope.filePickerOptions.allowMultiple)) {
                        // Show error info and init dropzone
                        scope.setDropZoneMsg('Multiple file selection is not allowed', true);
                    } else {
                        scope.setFilesArray(e.originalEvent.dataTransfer.files);

                        var areFilesValid = scope.validateFiles();
                        if (areFilesValid) {
                            // Show progress and upload
                            scope.clearDropZone();
                            angular.forEach(scope.filesArray, function (file, idx) {
                                // Show file upload progress inside the drop zone
                                var progressBar = angular.element('<upload-progress show-file-details="true" file-index="' + idx + '"></upload-progress>');
                                $compile(progressBar)(scope);
                                scope.addUploadProgressToDropZone(progressBar);

                                // Sum files size
                                scope.totalSize += file.size;
                            });

                            // Disable file browsing button
                            $('.btn-file').addClass('disabled');

                            scope.uploadAll();
                        } else {
                            scope.setDropZoneMsg(scope.fileValidationError, true);
                        }
                    }
                }
			});

            scope.resetDropZone = function() {
                scope.setFilesArray([]);
                $('.btn-file').removeClass('disabled');
                elem.removeClass('drag-active');
                elem.removeClass('has-error');

                elem.html(scope.dropZoneText);
            };

            scope.clearDropZone = function() {
                elem.removeClass('has-error');
                elem.html('');
            };

            scope.setDropZoneMsg = function(msg, isError) {
                scope.resetDropZone();
                if (isError) {
                    elem.addClass('has-error');
                }
                elem.html(msg);
            };

            scope.addUploadProgressToDropZone = function(uploadProgress) {
                elem.append(uploadProgress);
            };

            // Init drop zone text if none provided
            if (!scope.dropZoneText) {
                if(scope.filePickerOptions && scope.filePickerOptions.allowMultiple) {
                    scope.dropZoneText = 'Drag files here';
                } else {
                    scope.dropZoneText = 'Drag file here';
                }
            }

            scope.resetDropZone();
		}
	};
}]);

// File picker directive
// Accepts 'allow-multiple' as an attribute, if true - enables multiple file selection (default is false)
angular.module('filePickerApp').directive('fileSelect', ['$timeout', 'filePickerCommon', function($timeout, filePickerCommon) {
	return {
		restrict: 'E',
		template:   '<div file-drop ng-class="{\'clickable\': clickableDropZone && !getUploadInProgressStatus()}" ng-click="openBrowseFilesFromDropZone()"></div>' +
                    '<input type="file" name="file" file-browse ng-if="!filePickerOptions.allowMultiple && clickableDropZone" ng-hide="true">' +
                    '<input type="file" name="file" file-browse multiple ng-if="filePickerOptions.allowMultiple && clickableDropZone" ng-hide="true">' +
                    '<div class="form-group" ng-if="!dropZoneOnly">' +
                        '<span>OR Select a file to upload: </span>' +
                        '<span class="{{ okButtonClass + \' btn-file\'}}">' +
                            'Choose File<span ng-show="filePickerOptions.allowMultiple">s</span> <input type="file" name="file" file-browse ng-hide="filePickerOptions.allowMultiple">' +
                                        '<input type="file" name="file" file-browse multiple ng-show="filePickerOptions.allowMultiple">' +
                        '</span>' +
                    '</div>',
        scope: {
            okButtonClass: '@?',         //inner confirmation buttons class
            cancelButtonClass: '@?',     //inner cancellation buttons class
            filePickerOptions: '=',      //file options - length, types and mimes restrictions
            imageAreaSelectOptions: '=?',//options for imgAreaSelect
            imageOptions: '=?',          //image options ({minWidth, minHeight, maxWidth, maxHeight})
            onSuccessCallback: '&',      //callback function to be called when file was uploaded successfully.
            inkBlob: '=?',               //selected files inkBlob data
            dropZoneOnly: '=?',          //if true, show drop zone only without the file-browse button
            dropZoneText: '@?',          //optional initial drop zone text
            clickableDropZone: '@?',     //if true, clicking the dropzone will open a file browse window
            filePickModal: '=?'          //passed from the file-select-modal directive so we can control the modal from this directive
        },
        require: '?ngModel', // No need for ngModel when using file-select-modal
        controller: 'uploadCtrl',
		link: function(scope, elem, attrs, ngModelCtrl) {
            // Input validations (if not done in file-select-modal directive)
            if (!scope.filePickModal) {
                $timeout(function () {
                    if (!scope.filePickerOptions) {
                        scope.filePickerOptions = {};
                    }
                    // init defaults
                    scope.filePickerOptions.allowMultiple = scope.filePickerOptions.allowMultiple === undefined ? false : scope.filePickerOptions.allowMultiple;
                    scope.filePickerOptions.crop = scope.filePickerOptions.crop === undefined ? false : scope.filePickerOptions.crop;

                    // Remove trailing slash from path if provided with one
                    if (scope.filePickerOptions.path && scope.filePickerOptions.path.indexOf('/') === scope.filePickerOptions.path.length - 1) {
                        scope.filePickerOptions.path = scope.filePickerOptions.path.substr(0, scope.filePickerOptions.path.length - 1);
                    }

                    // Can't provide both crop=true and allowMultiple=true
                    if (scope.filePickerOptions.allowMultiple && scope.filePickerOptions.crop) {
                        throw new TypeError('Can\'t provide both crop=true and allowMultiple=true at the same time.');
                    }

                    // Can't provide imageOptions without crop=true, image size is validated only after opening the crop modal
                    if (!scope.filePickerOptions.crop && (scope.imageOptions && (scope.imageOptions.minWidth || scope.imageOptions.minHeight
                        || scope.imageOptions.maxWidth || scope.imageOptions.maxHeight))) {
                        throw new TypeError('Can\'t provide imageOptions without setting filePickerOptions.crop to true.');
                    }
                }, 0);
            }

            // Set default button classes if none provided
            scope.okButtonClass = scope.okButtonClass || 'btn btn-primary';
            scope.cancelButtonClass = scope.cancelButtonClass || 'btn btn-primary';

            scope.onSuccessCallback = scope.onSuccessCallback || function(){};

            // This function is called when upload is done (incl. crop) and was done not via the file-select-modal
            scope.onDoneUploading = function() {
                if (scope.filePickerOptions.allowMultiple) {
                    ngModelCtrl.$setViewValue(filePickerCommon.getUploadedFilesUrls());
                    scope.inkBlob = filePickerCommon.getUploadedFilesBlobs();
                } else {
                    ngModelCtrl.$setViewValue(filePickerCommon.getUploadedFilesUrls()[0]);
                    scope.inkBlob = filePickerCommon.getUploadedFilesBlobs()[0];
                }

                scope.resetDropZone();
            };

            scope.openBrowseFilesFromDropZone = function() {
                if (scope.clickableDropZone && !scope.getUploadInProgressStatus()) {
                    // Create a cloned element in place so the input value is refreshed (allow choosing same file over and over)
                    var inputElm = elem.find('input[type=file]');
                    inputElm.replaceWith( inputElm = inputElm.clone( true ) );

                    // Reset all errors and init helper vars
                    scope.resetDropZone();

                    inputElm.trigger('click');
                }
            };

            scope.getUploadInProgressStatus = filePickerCommon.getUploadInProgressStatus;
		}
	};
}]);

// File picker modal directive
// Accepts same attributes as fileSelect directive
angular.module('filePickerApp').directive('fileSelectModal', ['$compile', '$timeout', '$window', '$modal', 'filePickerCommon', function($compile, $timeout, $window, $modal, filePickerCommon) {
	return {
		restrict: 'E',
		template:   '<button type="button" ng-click="filePickModalFunc()" class="{{ buttonClass }}">' +
                        '<i class="{{buttonIcon}}" ng-show="buttonIcon"></i> ' +
                        '{{buttonText}}' +
                    '</button>',
        scope: {
            buttonClass: '@',            //every button can have different class
            buttonText: '@',             //the text of the button
            buttonIcon: '@',             //the icon of the button
            okButtonClass: '@?',         //inner confirmation buttons class
            cancelButtonClass: '@?',     //inner cancellation buttons class
            filePickerOptions: '=',      //file options - length, types and mimes restrictions
            imageAreaSelectOptions: '=?',//options for imgAreaSelect
            imageOptions: '=?',          //image options ({minWidth, minHeight, maxWidth, maxHeight})
            filePickModalFunc: '=?',     //outside function to bind the inner function for opening modal.
            onSuccessCallback: '&',      //callback function to be called when file was uploaded successfully.
            inkBlob: '=?'                //selected files inkBlob data
        },
        require: 'ngModel',
        controller: 'uploadCtrl',
		link: function(scope, elem, attrs, ngModelCtrl) {
            // Input validations
            $timeout(function(){
                if (!scope.filePickerOptions) {
                    scope.filePickerOptions = {};
                }
                // init defaults
                scope.filePickerOptions.allowMultiple = scope.filePickerOptions.allowMultiple === undefined ? false : scope.filePickerOptions.allowMultiple;
                scope.filePickerOptions.crop = scope.filePickerOptions.crop === undefined ? false : scope.filePickerOptions.crop;

                // Remove trailing slash from path if provided with one
                if (scope.filePickerOptions.path && scope.filePickerOptions.path.indexOf('/') === scope.filePickerOptions.path.length - 1) {
                    scope.filePickerOptions.path = scope.filePickerOptions.path.substr(0, scope.filePickerOptions.path.length - 1);
                }

                // Can't provide both crop=true and allowMultiple=true
                if (scope.filePickerOptions.allowMultiple && scope.filePickerOptions.crop) {
                    throw new TypeError('Can\'t provide both crop=true and allowMultiple=true at the same time.');
                }

                // Can't provide imageOptions without crop=true, image size is validated only after opening the crop modal
                if (!scope.filePickerOptions.crop && (scope.imageOptions && (scope.imageOptions.minWidth || scope.imageOptions.minHeight
                    || scope.imageOptions.maxWidth || scope.imageOptions.maxHeight))) {
                    throw new TypeError('Can\'t provide imageOptions without setting filePickerOptions.crop to true.');
                }
            }, 0);

            // Create the file pick modal and show it
            scope.createFilePickModal = function () {
                scope.initUpload();

                // Disabled state for modal close button didn't work so we do it manually
                scope.closeFilePickerModal = function() {
                    if (!filePickerCommon.getUploadInProgressStatus()) {
                        scope.filePickModal.dismiss();
                    }
                };

                scope.getUploadInProgressStatus = filePickerCommon.getUploadInProgressStatus;
                
                // If crop is not needed, cropDone is initialized with true
                var cropDone = scope.filePickerOptions.crop ? false : true;
                filePickerCommon.setCropDone(cropDone);

                var filePickModalHtml =
								'<div class="modal-header">' +
									'<button type="button" class="close" ng-click="closeFilePickerModal()">' +
										'<span aria-hidden="true">&times;</span><span class="sr-only">Close</span>' +
									'</button>' +
									'<h4 class="modal-title">Choose file to upload</h4>' +
								'</div>' +
								'<div class="modal-body">' +
									'<file-select ok-button-class="{{okButtonClass}}"' +
                                        'cancel-button-class="{{cancelButtonClass}}"' +
                                        'file-picker-options="filePickerOptions"' +
                                        'image-area-select-options="imageAreaSelectOptions"' +
                                        'image-options="imageOptions"' +
                                        'on-success-callback="onSuccessCallback"' +
                                        'ink-blob="inkBlob"' +
                                        'file-pick-modal="filePickModal">' +
                                    '</file-select>' +
								'</div>';

                scope.showFilePickModal = function() {
                    scope.filePickModal = $modal.open({
                        template: filePickModalHtml,
                        scope: scope,
                        backdrop: 'static',
                        keyboard: false
                    });
                    scope.filePickModal.opened.then(function() {
                        // The use of two modals (pick&crop) can cause 'modal-open' class not being added to body so we add it manually
                        $('body').addClass('modal-open');
                    });

                    var onModalClose = function() {
                        // Update model on closing (and if crop was needed and done)
                        if (filePickerCommon.getCropDone() && filePickerCommon.getUploadedFilesUrls().length) {
                            if (scope.filePickerOptions.allowMultiple) {
                                ngModelCtrl.$setViewValue(filePickerCommon.getUploadedFilesUrls());
                                scope.inkBlob = filePickerCommon.getUploadedFilesBlobs();
                            } else {
                                ngModelCtrl.$setViewValue(filePickerCommon.getUploadedFilesUrls()[0]);
                                scope.inkBlob = filePickerCommon.getUploadedFilesBlobs()[0];
                            }
                        }
                    };
                    scope.filePickModal.result.then(
                        function() {
                            onModalClose();
                        },
                        function() {
                            onModalClose();
                        }
                    );
                };
                scope.showFilePickModal();
            };

            // user have an option to pass an function from outside that will
            // launch the modal.
            // this makes embedding into other templates easier;
            scope.filePickModalFunc = scope.createFilePickModal;
		}
	};
}]);

// Progress bar directive (shows up when upload initiates)
// Accepts 'show-file-details' as attribute
angular.module('filePickerApp').directive('uploadProgress', function() {
	return {
		restrict: 'E',
		scope: true,
		template: '<div ng-show="showProgress" class="progress-container">' +
					'<div class="progress">' +
						'<div class="progress-bar progress-bar-striped active" role="progressbar" aria-valuenow="{{uploadProgress[idx]}}"' +
						  'aria-valuemin="0" aria-valuemax="100" ng-style="{width : ( uploadProgress[idx] + \'%\' ) }">' +
							'{{uploadProgress[idx]}}%' +
						'</div>' +
					'</div>' +
					'<div ng-show="showFileDetails" class="file-details">' +
						'<img ng-src="" alt="Your file image" />' +
						'<span>  {{filename}} | Size: {{filesize / 1024 / 1024 | number:2}}Mb | Modified: {{modified | date:\'MM/dd/yyyy\'}}</span>' +
					'</div>' +
				  '</div>',
		link: function(scope, elem, attrs) {
			scope.showFileDetails = attrs.showFileDetails;
			scope.idx = attrs.fileIndex;

            scope.filename = attrs.filename || scope.filesArray[scope.idx].name;
            scope.filesize = attrs.filesize || scope.filesArray[scope.idx].size;
            scope.modified = attrs.modified || scope.filesArray[scope.idx].lastModifiedDate;

            // Init uploadProgress
            scope.uploadProgress[scope.idx] = 0;
		}
	};
});

angular.module('filePickerApp').directive('imgOnLoad', function(){
    return {
        restrict: 'A',
        scope: {
            imgOnLoad: '&'
        },
        link: function(scope, element) {
            element.bind('load', function() {
                scope.imgOnLoad();
            });
        }
    };
});

angular.module('filePickerApp').directive('cropAreaModal', ['$timeout', '$compile', '$modal', 'filePickerCommon', function($timeout, $compile, $modal, filePickerCommon) {
    return {
		restrict: 'E',
		link: function(scope, elem, attrs) {
			scope.imagePath = attrs.imagePath;
            scope.doneLoadingImage = false;
            scope.cropModalHeader = 'Loading image, please wait...';

            var cropModalTemplate = '<div class="modal-header">' +
                                        '<h4 class="modal-title"><i class="fa fa-spinner fa-spin" ng-hide="doneLoadingImage"></i> {{cropModalHeader}}</h4>' +
                                    '</div>' +
                                    '<div class="modal-body">' +
                                        '<div id="image-to-crop-parent">' + // Id used for fixing imgAreaSelect bug with modals
                                            '<img id="image-to-crop" img-on-load="cropModalInit()" ng-src="{{imagePath}}" alt="Image to crop" width="100%">' +
                                        '</div>' +
                                    '</div>' +
                                    '<div class="modal-footer">' +
                                        '<button type="button" class="{{cancelButtonClass}}" ng-click="cancelCrop()">Cancel</button>' +
                                        '<button type="button" class="{{okButtonClass}}" ng-click="doCrop()" ng-class="areaBox.width === 0 || !areaBox.width ? \'disabled\' : \'\'">Save</button>' +
                                    '</div>';

            scope.cropModal = $modal.open({
                template: cropModalTemplate,
                scope: scope,
                backdrop: 'static',
                keyboard: false
            });
            scope.cropModal.opened.then(function(){
                // The use of two modals (pick&crop) can cause 'modal-open' class not being added to body so we add it manually
                $('body').addClass('modal-open');
            });

            // This function is called once the image to crop is fully loaded and apply imgAreaSelect on it
            scope.cropModalInit = function() {
                scope.doneLoadingImage = true;
                scope.cropModalHeader = 'Select crop area';

                // Apply scope to force image load on screen before imgAreaSelect checks it's visual height and width
                scope.$apply();

                var image = document.getElementById('image-to-crop');

                // Now that we have an image url we can test for image size
                var isImageSizeValid = scope.validateImageSize(image);
                if (!isImageSizeValid) {
                    // Restore this when we support DELETE in CORS config
//                    scope.deleteUncroppedFile();

                    // Don't let user crop image, show error and let user pick another file
                    filePickerCommon.setUploadInProgress(false);
                    scope.setDropZoneMsg(scope.imageValidationError , true);
                    scope.cropModal.dismiss();
                } else {
                    // Image size is valid, let user select crop area
                    var imgAreaSelectOptions = angular.extend({},
                        scope.imageAreaSelectOptions,
                        {
                            onSelectEnd: function (img, selection) {
                                scope.areaBox = {
                                    x1: selection.x1,
                                    y1: selection.y1,
                                    x2: selection.x2,
                                    y2: selection.y2,
                                    width: selection.width,
                                    height: selection.height
                                };
                                scope.$apply(); // For updating 'save crop' button state
                            },
                            // Fix for updating 'save crop' button disabled/enabled state when modal opens
                            onInit: function (img, selection) {
                                scope.areaBox = {
                                    x1: selection.x1,
                                    y1: selection.y1,
                                    x2: selection.x2,
                                    y2: selection.y2,
                                    width: selection.width,
                                    height: selection.height
                                };
                                scope.$apply();
                            },
                            parent: '#image-to-crop-parent',
                            handles: true,
                            imageWidth: image.naturalWidth,
                            imageHeight: image.naturalHeight
                        }
                    );
                    angular.element(image).imgAreaSelect(imgAreaSelectOptions);
                }
            };

            scope.doCrop = function() {
                // Do crop only if a crop area was selected
                if (scope.areaBox.width !== 0) {
                    // Build edit params for image edit function
                    var fileEditParams =
                        {
                            cropX: scope.areaBox.x1,
                            cropY: scope.areaBox.y1,
                            cropWidth: scope.areaBox.width,
                            cropHeight: scope.areaBox.height,
                            finalWidth: scope.areaBox.width,
                            finalHeight: scope.areaBox.height
                        };

                    // The callback function for image edit function
                    var imageEditCallback = function(croppedImageBlob) {
                        // Update cropDone param in controller
                        filePickerCommon.setCropDone(true);

                        // Reset areaBox
                        scope.areaBox = {};

                        // Show progress of cropped file uploading
                        scope.clearDropZone();
                        var progressBar = angular.element('<upload-progress show-file-details="true" file-index="0" filename="' + scope.filesArray[0].name + '" filesize="' + croppedImageBlob.size + '" modified="' + new Date().getTime() + '"></upload-progress>');
                        $compile(progressBar)(scope);
                        scope.addUploadProgressToDropZone(progressBar);
                        // Sum files size
                        scope.totalSize = croppedImageBlob.size;

                        scope.$apply();

                        // Upload file again
                        scope.upload(croppedImageBlob, 0);
                    };

                    scope.editImage(scope.filesArray[0], fileEditParams, imageEditCallback);
                }

                scope.cropModal.close();
            };

            scope.cancelCrop = function() {
                // Restore this when we support DELETE in CORS config
                // Delete uncropped uploaded file
//                scope.deleteUncroppedFile();

                // Hide cropping modal and remove file select and upload elements
                scope.cropModal.result.then(
                    function(){

                    },
                    function() {
                        if (scope.filePickModal) {
                            scope.filePickModal.dismiss();
                        }
                    }
                );
                scope.cropModal.dismiss();
            };
		}
	};
}]);

// Service for file picker params
angular.module('filePickerApp').service('filePickerParams', function(){
	var creds = {};

	var setCredentials = function(bucketName, accessKey, secretKey) {
		creds = {
			bucket: bucketName,
			accessKey: accessKey,
			secretKey: secretKey
		};
	};

	var getCredentials = function() {
		return creds;
	};

    var onSuccessCallback = function() {};

	return {
		setCredentials: setCredentials,
		getCredentials: getCredentials,
        onSuccessCallback: onSuccessCallback
	};
});

// Service for common vars
angular.module('filePickerApp').service('filePickerCommon', function(){
    // Uploaded Files Array
	var uploadedFilesUrls = [];

	var pushUploadedFileUrl = function(newUrl) {
		uploadedFilesUrls.push(newUrl);
	};

	var getUploadedFilesUrls = function() {
		return uploadedFilesUrls;
	};

    var setUploadedFileUrl = function(newUrl, idx) {
        uploadedFilesUrls[idx] = newUrl;
    }

    var initUploadedFilesUrls = function() {
        uploadedFilesUrls = [];
    };

    // Uploaded Files Blobs Array
    var uploadedFilesBlobs = [];

	var pushUploadedFileBlob = function(newBlob) {
		uploadedFilesBlobs.push(newBlob);
	};

	var getUploadedFilesBlobs = function() {
		return uploadedFilesBlobs;
	};

    var initUploadedFilesBlobs = function() {
        uploadedFilesBlobs = [];
    };

    // Uploaded In Progress Indication
    var isUploadInProgress = false;

    var setUploadInProgress = function(newVal) {
        isUploadInProgress = newVal;
    };

    var getUploadInProgressStatus = function() {
        return isUploadInProgress;
    };

    // Crop Done Indication
    var cropDone = false;

    var setCropDone = function(newVal) {
        cropDone = newVal;
    };
    var getCropDone = function() {
        return cropDone;
    };

	return {
		pushUploadedFileUrl: pushUploadedFileUrl,
		getUploadedFilesUrls: getUploadedFilesUrls,
        setUploadedFileUrl: setUploadedFileUrl,
        initUploadedFilesUrls: initUploadedFilesUrls,
        pushUploadedFileBlob: pushUploadedFileBlob,
		getUploadedFilesBlobs: getUploadedFilesBlobs,
        initUploadedFilesBlobs: initUploadedFilesBlobs,
        setUploadInProgress: setUploadInProgress,
        getUploadInProgressStatus: getUploadInProgressStatus,
        setCropDone: setCropDone,
        getCropDone: getCropDone
	};
});

// --- Controller --- //
angular.module('filePickerApp').controller('uploadCtrl', ['$scope', '$compile', '$timeout', 'filePickerParams', 'filePickerCommon', function($scope, $compile, $timeout, filePickerParams, filePickerCommon) {
	var initialUrl = 's3.amazonaws.com';
	var creds = filePickerParams.getCredentials();

	// Init all upload params
	$scope.initUpload = function() {
        filePickerCommon.setUploadInProgress(false);
		$scope.showProgress = false;
		$scope.uploadProgress = [];
		$scope.filesArray = [];
		$scope.totalSize = 0;
		$scope.totalProgress = 0;
        // Init filesProcessed counter
        $scope.filesProcessed = 0;

        filePickerCommon.initUploadedFilesUrls();
        filePickerCommon.initUploadedFilesBlobs();
	};
//	$scope.initUpload();

    $scope.setFilesArray = function (filesArray) {
        $scope.filesArray = filesArray;
    };
    $scope.getFilesArray = function() {
        return $scope.filesArray;
    };

    $scope.validateFiles = function() {
        $scope.fileValidationError = undefined;

        // Validate files size (shouldn't be 0)
        for (var i = 0; i < $scope.filesArray.length; i++) {
            if ($scope.filesArray[i].size === 0) {
                $scope.fileValidationError = 'Selected file is empty';
                return false;
            }
        }

        // Validate file type if restriction provided
        if ($scope.filePickerOptions.allowedTypes !== undefined) {
            for (var i = 0; i < $scope.filesArray.length; i++) {
                if ($scope.filePickerOptions.allowedTypes.indexOf($scope.filesArray[i].name.split('.').pop()) === -1 ) {
                    $scope.fileValidationError = 'Selected file extension (' + $scope.filesArray[i].name.split('.').pop() + ') is not allowed. <br>' +
                        'Allowed types are: ' + $scope.filePickerOptions.allowedTypes;
                    return false;
                }
            }
        }

        // Validate mime type if restriction provided
        var fileIdx = 0;
        if ($scope.filePickerOptions.allowedMimes !== undefined) {
            for (fileIdx = 0; fileIdx < $scope.filesArray.length; fileIdx++) {
                var mimeVerified = false;

                for (var mimeIdx = 0; mimeIdx < $scope.filePickerOptions.allowedMimes.length; mimeIdx++) {
                    var currentMime = $scope.filePickerOptions.allowedMimes[mimeIdx];

                    // If a generic mime was provided, check if the file fits its pattern
                    if (currentMime.substr(currentMime.length - 2) === '/*') {
                        if ($scope.filesArray[fileIdx].type.indexOf(currentMime.substr(0, currentMime.length - 1)) !== -1) {
                            mimeVerified = true;
                        }
                    // else, we need to make a full comparison
                    } else if ($scope.filesArray[fileIdx].type === currentMime) {
                        mimeVerified = true;
                    }
                }

                if (!mimeVerified) {
                    var type = $scope.filesArray[fileIdx].type || $scope.filesArray[fileIdx].name.split('.').pop();
                    $scope.fileValidationError = 'Selected file type (' + type + ') is not allowed.<br>' +
                        'Allowed mime types are: ' + $scope.filePickerOptions.allowedMimes;
                    return false;
                }
            }
        }

        // Validate excluded mime types if restriction provided
        if ($scope.filePickerOptions.excludedMimes !== undefined) {
            for (fileIdx = 0; fileIdx < $scope.filesArray.length; fileIdx++) {
                if ($scope.filePickerOptions.excludedMimes.indexOf(($scope.filesArray[fileIdx].type)) !== -1) {
                    var type = $scope.filesArray[fileIdx].type || $scope.filesArray[fileIdx].name.split('.').pop();
                    $scope.fileValidationError = 'Selected file type (' + type + ') is not allowed.<br>' +
                        'The following mime types are not allowed: ' + $scope.filePickerOptions.excludedMimes;
                    return false;
                }
            }
        }

        // Validate filename length
        if ($scope.filePickerOptions.maxFilenameLength) {
            for (fileIdx = 0; fileIdx < $scope.filesArray.length; fileIdx++) {
                if ($scope.filesArray[fileIdx].name.length > $scope.filePickerOptions.maxFilenameLength) {
                    $scope.fileValidationError = 'Selected file name is ' + $scope.filesArray[fileIdx].name.length + ' characters long.<br>' +
                        'Maximum file name length allowed is ' + $scope.filePickerOptions.maxFilenameLength + ' characters.';
                    return false;
                }
            }
        }

        return true;
    };

    $scope.validateImageSize = function(image) {
        $scope.imageValidationError = undefined;

        if ($scope.imageOptions) {
            if (($scope.imageOptions.minWidth && $scope.imageOptions.minWidth > image.naturalWidth) ||
                ($scope.imageOptions.minHeight && $scope.imageOptions.minHeight > image.naturalHeight)) {
                $scope.imageValidationError = 'Image size is too small (' + image.naturalWidth + 'x' + image.naturalHeight + '). Please select an image that is at least ' + $scope.imageOptions.minWidth + ' pixels wide and at least ' + $scope.imageOptions.minHeight + ' pixels tall.';
                return false;
            }

            if (($scope.imageOptions.maxWidth && $scope.imageOptions.maxWidth < image.naturalWidth) ||
                ($scope.imageOptions.maxHeight && $scope.imageOptions.maxHeight < image.naturalHeight)) {
                $scope.imageValidationError = 'Image size is too large (' + image.naturalWidth + 'x' + image.naturalHeight + '). Please select an image with a maximum width of ' + $scope.imageOptions.minWidth + ' pixels and a maximum height of ' + $scope.imageOptions.minHeight + ' pixels.';
                return false;
            }
        }

        return true;
    };

	$scope.uploadAll = function() {
		if ($scope.filesArray.length) {

			$scope.showProgress = true;

            angular.forEach($scope.filesArray, function(file, idx) {
                    $scope.upload(file, idx);
            });
		} else {
			// No File Selected
			console.log('No File Selected');
		}
	};

	$scope.upload = function(file, idx) {
        filePickerCommon.setUploadInProgress(true);

        var requestedPathAddition = $scope.filePickerOptions.path ? '/' + $scope.filePickerOptions.path : '';
		// Configure The S3 Object
		var bucket = new AWS.S3({
			params: { Bucket: creds.bucket + requestedPathAddition },
			credentials: { accessKeyId: creds.accessKey, secretAccessKey: creds.secretKey }
		});
        bucket.getBucketLocation({Bucket: creds.bucket}, function(err){
            if (err) {
                console.log(err);
            }
        });

        var startUpload = function() {
            // Append timestamp to file for uniqeness
            var uniqueFileName = new Date().getTime() + '-' + $scope.filesArray[idx].name;
            // Restore this when we support DELETE in CORS config
            // delete old file (pre-cropped)
    //            if ($scope.filePickerOptions.crop && $scope.cropDone) {
    //                $scope.deleteUncroppedFile();
    //            }

            // Save filename in scope (for delete function)
            $scope.uniqueFileName = uniqueFileName;

            var params = { Key: uniqueFileName, ACL: 'public-read', ContentType: file.type, Body: file, ServerSideEncryption: 'AES256' };

            bucket.putObject(params, function(err) {
                $timeout(function(){
                    if(err) {
                        // Handle error
                        console.log('S3 putObject returned error: ' + err);

                        filePickerCommon.setUploadInProgress(false);
                        $scope.setDropZoneMsg('Error uploading file, please try again', true);

                        // Mark crop as done for imitating full upload process completion (closing the upload modal will remove it)
                        filePickerCommon.setCropDone(true);
                    } else {
                        // Success!
                        var bucketInitialAddress,
                            bucketFoldersPath;
                        if (creds.bucket.indexOf('/') !== -1) {
                            bucketInitialAddress = creds.bucket.substr(0, creds.bucket.indexOf('/'));
                            bucketFoldersPath = creds.bucket.substr(creds.bucket.indexOf('/'));
                        } else {
                            bucketInitialAddress = creds.bucket;
                            bucketFoldersPath = '';
                        }

                        if ($scope.filePickerOptions.path) {
                            bucketFoldersPath += '/' + $scope.filePickerOptions.path;
                        }

                        // Build uploaded file url and handle url breaking chars in filename
                        filePickerCommon.setUploadedFileUrl('https://' + bucketInitialAddress + '.' + initialUrl + bucketFoldersPath + '/' + encodeURIComponent(uniqueFileName).replace('\'', '%27'), idx);

                         // Update inkBlob
                        filePickerCommon.pushUploadedFileBlob({
                            filename: file.name,
                            size: file.size
                        });

                        $scope.$digest();

                        $scope.filesProcessed++;

                        // Close files upload modal when done uploading all files and reset drop-zone
                        if ($scope.filesProcessed === $scope.filesArray.length) {
                            // Handle crop area selection if needed
                            if ($scope.filePickerOptions.crop && !filePickerCommon.getCropDone()) {
                                // Init files processed counter and filesBlob array as they will be calculated and rebuilded after crop
                                $scope.filesProcessed = 0;
                                filePickerCommon.initUploadedFilesBlobs();

                                // Open the crop modal
                                $compile('<crop-area-modal image-path="' + filePickerCommon.getUploadedFilesUrls()[0] + '"></crop-area-modal>')($scope);
                            } else {
                                // Run callbacks and close modal
                                filePickerCommon.setUploadInProgress(false);

                                // Call supplied callback
                                $timeout($scope.onSuccessCallback, 0);

                                filePickerParams.onSuccessCallback(filePickerCommon.getUploadedFilesUrls());

                                if ($scope.filePickModal) {
                                    $scope.filePickModal.close();
                                } else {
                                    $scope.onDoneUploading();
                                }
                            }
                        }
                    }
                }, 100); // This timeout function solves an issue with firefox where the async requests are being messed up

            })
            .on('httpUploadProgress',function(progress) {
                // Calc file progress
                $scope.uploadProgress[idx] = Math.round(progress.loaded / progress.total * 100);

                $scope.$digest();
            });
        };

        // Set progress data - file preview (if file is image)
		if (file.type.indexOf('image/') !== -1) {
			var reader = new FileReader();
			reader.onload = function (e) {
                // Test image validity, upload if valid, show error if not
                $('.file-details img').eq(idx)[0].onload = function(){
                    startUpload();
                };
                $('.file-details img').eq(idx)[0].onerror = function(){
                    // Something is wrong with the image file (the browser can't read it)
                    filePickerCommon.setUploadInProgress(false);
                    $scope.setDropZoneMsg('Something is wrong with the image file, please try to upload a different file compatible with your browser.' , true);
                };
				$('.file-details img').eq(idx).attr('src', e.target.result);
			};
			reader.readAsDataURL(file);
		} else {
			// Hide image preview
			$('.file-details img').eq(idx).hide();

            startUpload();
		}
	};

    // Restore this once we allow DELETE in buckets' CORS configuration
//    $scope.deleteUncroppedFile = function () {
//        // Send delete request only if we have a unique file name stored in scope
//        if ($scope.uniqueFileName) {
//            // Configure The S3 Object
//            var s3object = new AWS.S3({
//                params: { Bucket: creds.bucket },
//                credentials: { accessKeyId: creds.accessKey, secretAccessKey: creds.secretKey }
//            });
//            s3object.getBucketLocation({Bucket: creds.bucket}, function(err){
//                if (err) {
//                    console.log(err);
//                }
//            });
//
//            var params = { Bucket: creds.bucket, Key: $scope.uniqueFileName};
//
//            s3object.deleteObject(params, function (err) {
//                if (err) {
//                    console.log('error deleting temp uncropped file: ' + err);
//                }
//            });
//        }
//    };

    // Resize and crop image
    // Edit params structure:
    //    {
    //        cropX: n,
    //        cropY: n,
    //        cropWidth: n,
    //        cropHeight: n,
    //        finalWidth: n,
    //        finalHeight: n
    //    }
    // If no resize params given (finalWidth/finalHeight), use original image size or crop size if provided
    // If no crop params given, just resize
	$scope.editImage = function (imageFile, editParams, callback) {
		var reader = new FileReader();
		reader.onload = function (e) {
			// Create an image object from file
			var image = new Image();
			// Make sure the image is fully loaded before manipulating
			image.onload = function() {
                // Init final size params if not provided
                if (editParams.finalWidth === undefined || editParams.finalWidth === 0) {
                    editParams.finalWidth = editParams.cropWidth || image.width;
                }
                if (editParams.finalHeight === undefined || editParams.finalHeight === 0) {
                    editParams.finalHeight = editParams.cropHeight || image.height;
                }
                if (editParams.cropWidth === 0) {
                    editParams.cropWidth = image.width;
                }
                if (editParams.cropHeight === 0) {
                    editParams.cropHeight = image.height;
                }

				// Create a canvas with requested dimensions
				var canvas = $('<canvas width="' + editParams.finalWidth + '" height="' + editParams.finalHeight +'"/>');
				var ctx = canvas.get(0).getContext('2d');

				// Draw the image in the new canvas
				var nativeImage = image.impl ? image.impl : image;
				ctx.drawImage(nativeImage, editParams.cropX, editParams.cropY, editParams.cropWidth,
					editParams.cropHeight, 0, 0, editParams.finalWidth, editParams.finalHeight);

				// Build file object from canvas and return it
				var dataURI = canvas.get(0).toDataURL(imageFile.type);

				callback(dataURItoBlob(dataURI));
			};
			image.src = e.target.result;
		};
		reader.readAsDataURL(imageFile);
	};

	var dataURItoBlob = function (dataURI) {
		// convert base64 to raw binary data held in a string
		var byteString = atob(dataURI.split(',')[1]);

		// separate out the mime component
		var mimeString = dataURI.split(',')[0].split(':')[1].split(';')[0];

		// write the bytes of the string to an ArrayBuffer
		var arrayBuffer = new ArrayBuffer(byteString.length);
		var ia = new Uint8Array(arrayBuffer);
		for (var i = 0; i < byteString.length; i++) {
			ia[i] = byteString.charCodeAt(i);
		}

		// write the ArrayBuffer to a blob
        var ua = window.navigator.userAgent,
            blob;

        if (ua.indexOf("MSIE ") !== -1 || !!navigator.userAgent.match(/Trident.*rv\:11\./)) {
            // IE, special blob handling
            var bb = new MSBlobBuilder();
            bb.append(arrayBuffer);
            blob = bb.getBlob(mimeString);
        } else {
            var dataView = new DataView(arrayBuffer);
		    blob = new Blob([dataView], {type: mimeString});
        }

		return blob;
	};
}]);