import 'dart:io';
import 'dart:typed_data';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';
import '../../core/constants.dart';
import '../../core/logger.dart';

class ApiService {
  Future<Uint8List?> uploadAndBlur({
    required XFile? pickedFile,
    required File? imageFile,
    required String blurType,
    Uint8List? maskBytes,
    int blurStrength = 30,
    String blurShape = 'rect',
    String blurStyle = 'smooth',
  }) async {
    AppLogger.info('Starting image upload and blur: type=$blurType, shape=$blurShape');
    var request = http.MultipartRequest('POST', Uri.parse(AppConstants.blurEndpoint));

    // Add image file
    if (pickedFile != null) {
      final bytes = await pickedFile.readAsBytes();
      request.files.add(http.MultipartFile.fromBytes(
        'file',
        bytes,
        filename: pickedFile.name,
      ));
    } else if (imageFile != null) {
      final bytes = await imageFile.readAsBytes();
      request.files.add(http.MultipartFile.fromBytes(
        'file',
        bytes,
        filename: imageFile.path.split('/').last,
      ));
    } else {
      AppLogger.error('No image provided for upload');
      throw Exception('No image provided');
    }

    // Add fields
    request.fields['blur_type'] = blurType;
    request.fields['blur_strength'] = blurStrength.toString();
    request.fields['blur_shape'] = blurShape;
    request.fields['blur_style'] = blurStyle;

    // Add mask if present
    if (maskBytes != null) {
      request.files.add(http.MultipartFile.fromBytes(
        'mask',
        maskBytes,
        filename: 'mask.png',
      ));
    }

    // Send request
    try {
      var response = await request.send();

      if (response.statusCode == 200) {
        AppLogger.info('Image processed successfully');
        return await response.stream.toBytes();
      } else {
        AppLogger.error('Failed to process image: ${response.statusCode}');
        throw Exception('Failed to process image: ${response.statusCode}');
      }
    } catch (e, stack) {
      AppLogger.error('Error during image upload', e, stack);
      rethrow;
    }
  }

  Future<Map<String, dynamic>> uploadVideo({
    required XFile videoFile,
    required String blurType,
    int blurStrength = 30,
    String blurShape = 'rect',
    String blurStyle = 'smooth',
  }) async {
    AppLogger.info('Starting video upload: ${videoFile.path}');
    var request = http.MultipartRequest('POST', Uri.parse(AppConstants.blurVideoEndpoint));

    final bytes = await videoFile.readAsBytes();
    request.files.add(http.MultipartFile.fromBytes(
      'file',
      bytes,
      filename: videoFile.name,
    ));

    request.fields['blur_type'] = blurType;
    request.fields['blur_strength'] = blurStrength.toString();
    request.fields['blur_shape'] = blurShape;
    request.fields['blur_style'] = blurStyle;

    try {
      var response = await request.send();
      final respStr = await response.stream.bytesToString();

      if (response.statusCode == 200) {
        AppLogger.info('Video uploaded successfully: $respStr');
        return jsonDecode(respStr);
      } else {
        AppLogger.error('Failed to upload video: ${response.statusCode}');
        throw Exception('Failed to upload video: ${response.statusCode}');
      }
    } catch (e, stack) {
      AppLogger.error('Error during video upload', e, stack);
      rethrow;
    }
  }

  Future<Map<String, dynamic>> checkVideoStatus(String jobId) async {
    try {
      final response = await http.get(Uri.parse('${AppConstants.videoStatusEndpoint}/$jobId'));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        AppLogger.error('Failed to check status: ${response.statusCode}');
        throw Exception('Failed to check status: ${response.statusCode}');
      }
    } catch (e) {
      AppLogger.error('Error checking video status', e);
      rethrow;
    }
  }
}
