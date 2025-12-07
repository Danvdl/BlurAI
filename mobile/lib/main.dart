import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:http/http.dart' as http;
import 'package:file_picker/file_picker.dart';
import 'package:device_preview/device_preview.dart';
import 'screens/mask_editor_screen.dart';

void main() {
  runApp(
    DevicePreview(
      enabled: !kReleaseMode,
      builder: (context) => const MyApp(), // Wrap your app
    ),
  );
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'BlurAI',
      locale: DevicePreview.locale(context),
      builder: DevicePreview.appBuilder,
      theme: ThemeData(
        primarySwatch: Colors.blue,
        visualDensity: VisualDensity.adaptivePlatformDensity,
      ),
      home: const MyHomePage(),
    );
  }
}

class MyHomePage extends StatefulWidget {
  const MyHomePage({super.key});

  @override
  State<MyHomePage> createState() => _MyHomePageState();
}

class _MyHomePageState extends State<MyHomePage> {
  File? _image;
  final picker = ImagePicker();
  String? _blurredImageUrl;
  bool _isLoading = false;
  bool _isVideo = false;
  XFile? _pickedFile; // Store XFile for web compatibility
  List<List<Offset>>? _mask; // Store the mask strokes

  Future<void> _pickImage() async {
    final pickedFile = await picker.pickImage(source: ImageSource.gallery);

    if (pickedFile != null) {
      setState(() {
        _pickedFile = pickedFile;
        _image = kIsWeb ? null : File(pickedFile.path);
        _blurredImageUrl = null;
        _isVideo = false;
        _mask = null;
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
          // On web, we'll handle bytes differently
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

  Future<void> _uploadAndBlur(String blurType) async {
    if (_pickedFile == null && _image == null) return;

    setState(() {
      _isLoading = true;
    });

    try {
      var request = http.MultipartRequest(
          'POST', Uri.parse('http://127.0.0.1:8000/blur-image'));
      
      // Use bytes for web compatibility
      if (_pickedFile != null) {
        final bytes = await _pickedFile!.readAsBytes();
        request.files.add(http.MultipartFile.fromBytes(
          'file',
          bytes,
          filename: _pickedFile!.name,
        ));
      } else if (_image != null) {
        final bytes = await _image!.readAsBytes();
        request.files.add(http.MultipartFile.fromBytes(
          'file',
          bytes,
          filename: _image!.path.split('/').last,
        ));
      }
      
      request.fields['blur_type'] = blurType;

      var response = await request.send();
      if (response.statusCode == 200) {
        // Save the blurred image
        final bytes = await response.stream.toBytes();
        
        setState(() {
          // For web, convert bytes to data URL
          if (kIsWeb) {
            _blurredImageUrl = Uri.dataFromBytes(bytes, mimeType: 'image/jpeg').toString();
          } else {
            // For native, save to temp file
            final tempDir = Directory.systemTemp;
            final file = File('${tempDir.path}/blurred_${DateTime.now().millisecondsSinceEpoch}.jpg');
            file.writeAsBytesSync(bytes);
            _image = file;
          }
          _isLoading = false;
        });
      } else {
        setState(() {
          _isLoading = false;
        });
        // Handle error
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Failed to process image')),
          );
        }
      }
    } catch (e) {
      setState(() {
        _isLoading = false;
      });
      // Handle error
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
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
            : _blurredImageUrl != null
                ? Image.network(_blurredImageUrl!)
                : _pickedFile == null && _image == null
                    ? const Text('No image selected.')
                    : kIsWeb && _pickedFile != null
                        ? Image.network(_pickedFile!.path)
                        : _image != null
                            ? Image.file(_image!)
                            : const Text('Error loading image'),
      ),
      bottomNavigationBar: BottomAppBar(
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
                icon: Icon(Icons.brush, color: _mask != null ? Colors.red : null),
                onPressed: () async {
                  if (_pickedFile != null) {
                    final result = await Navigator.push<List<List<Offset>>>(
                      context,
                      MaterialPageRoute(
                        builder: (context) => MaskEditorScreen(imageFile: _pickedFile!),
                      ),
                    );
                    if (result != null) {
                      setState(() {
                        _mask = result;
                      });
                    }
                  }
                },
                tooltip: 'Edit Mask',
              ),
              ElevatedButton(
                onPressed: () => _uploadAndBlur('background'),
                child: Text(_mask != null ? 'Blur Mask' : 'Blur BG'),
              ),
              ElevatedButton(
                onPressed: () => _uploadAndBlur('faces'),
                child: const Text('Blur Faces'),
              ),
            ]
          ],
        ),
      ),
    );
  }
}
