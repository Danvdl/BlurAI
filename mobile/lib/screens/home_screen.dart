import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:file_picker/file_picker.dart';
import '../data/services/api_service.dart';
import 'mask_editor_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final ApiService _apiService = ApiService();
  final ImagePicker _picker = ImagePicker();
  
  File? _image;
  XFile? _pickedFile; // Store XFile for web compatibility
  String? _blurredImageUrl;
  Uint8List? _maskBytes;
  
  bool _isLoading = false;
  bool _isVideo = false;

  Future<void> _pickImage() async {
    final pickedFile = await _picker.pickImage(source: ImageSource.gallery);

    if (pickedFile != null) {
      setState(() {
        _pickedFile = pickedFile;
        _image = kIsWeb ? null : File(pickedFile.path);
        _blurredImageUrl = null;
        _isVideo = false;
        _maskBytes = null;
      });
    }
  }

  Future<void> _pickVideo() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.video,
      allowMultiple: false,
      withData: true, // Need bytes for web
    );

    if (result != null) {
      setState(() {
        if (kIsWeb && result.files.single.bytes != null) {
          _image = null;
          _blurredImageUrl = null;
          _isVideo = true;
        } else if (result.files.single.path != null) {
          _image = File(result.files.single.path!);
          _blurredImageUrl = null;
          _isVideo = true;
        }
      });
    }
  }

  Future<void> _handleBlur(String blurType) async {
    if (_pickedFile == null && _image == null) return;

    setState(() => _isLoading = true);

    try {
      final bytes = await _apiService.uploadAndBlur(
        pickedFile: _pickedFile,
        imageFile: _image,
        blurType: blurType,
        maskBytes: _maskBytes,
      );

      if (bytes != null) {
        setState(() {
          if (kIsWeb) {
            _blurredImageUrl = Uri.dataFromBytes(bytes, mimeType: 'image/jpeg').toString();
          } else {
            final tempDir = Directory.systemTemp;
            final file = File('${tempDir.path}/blurred_${DateTime.now().millisecondsSinceEpoch}.jpg');
            file.writeAsBytesSync(bytes);
            _image = file;
          }
        });
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
      }
    } finally {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _openMaskEditor() async {
    if (_pickedFile != null) {
      final result = await Navigator.push<Uint8List>(
        context,
        MaterialPageRoute(
          builder: (context) => MaskEditorScreen(imageFile: _pickedFile!),
        ),
      );
      if (result != null) {
        setState(() {
          _maskBytes = result;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('BlurAI'),
      ),
      body: Center(
        child: _isLoading
            ? const CircularProgressIndicator()
            : _buildContent(),
      ),
      bottomNavigationBar: _buildBottomBar(),
    );
  }

  Widget _buildContent() {
    if (_blurredImageUrl != null) {
      return Image.network(_blurredImageUrl!);
    }
    if (_pickedFile == null && _image == null) {
      return const Text('No image selected.');
    }
    if (kIsWeb && _pickedFile != null) {
      return Image.network(_pickedFile!.path);
    }
    if (_image != null) {
      return Image.file(_image!);
    }
    return const Text('Error loading image');
  }

  Widget _buildBottomBar() {
    return BottomAppBar(
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: <Widget>[
          IconButton(
            icon: const Icon(Icons.photo_library),
            onPressed: _pickImage,
            tooltip: 'Pick Image',
          ),
          IconButton(
            icon: const Icon(Icons.video_library),
            onPressed: _pickVideo,
            tooltip: 'Pick Video',
          ),
          if ((_pickedFile != null || _image != null) && !_isVideo) ...[
            IconButton(
              icon: Icon(Icons.brush, color: _maskBytes != null ? Colors.red : null),
              onPressed: _openMaskEditor,
              tooltip: 'Edit Mask',
            ),
            ElevatedButton(
              onPressed: () => _handleBlur('background'),
              child: Text(_maskBytes != null ? 'Blur Mask' : 'Blur BG'),
            ),
            ElevatedButton(
              onPressed: () => _handleBlur('faces'),
              child: const Text('Blur Faces'),
            ),
          ]
        ],
      ),
    );
  }
}
