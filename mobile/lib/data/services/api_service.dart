import 'dart:io';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';
import '../../core/constants.dart';

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
    var response = await request.send();

    if (response.statusCode == 200) {
      return await response.stream.toBytes();
    } else {
      throw Exception('Failed to process image: ${response.statusCode}');
    }
  }
}
