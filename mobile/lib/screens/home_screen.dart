import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:video_player/video_player.dart';
import '../data/services/api_service.dart';
import '../widgets/modern_widgets.dart';
import '../core/theme.dart';
import '../core/constants.dart';
import '../core/logger.dart';
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
  XFile? _pickedFile;
  String? _blurredImageUrl;
  Uint8List? _maskBytes;
  VideoPlayerController? _videoController;
  
  bool _isLoading = false;
  bool _isVideo = false;
  
  double _blurStrength = 30.0;
  String _blurShape = 'rect'; // 'rect', 'oval', 'trace'
  String _blurStyle = 'smooth'; // 'smooth', 'pixelate'

  @override
  void dispose() {
    _videoController?.dispose();
    super.dispose();
  }

  Future<void> _pickImage() async {
    AppLogger.info('Picking image from gallery');
    final pickedFile = await _picker.pickImage(source: ImageSource.gallery);

    if (pickedFile != null) {
      AppLogger.info('Image picked: ${pickedFile.path}');
      _disposeVideoController();
      setState(() {
        _pickedFile = pickedFile;
        _image = kIsWeb ? null : File(pickedFile.path);
        _blurredImageUrl = null;
        _isVideo = false;
        _maskBytes = null;
      });
    } else {
      AppLogger.info('Image picking cancelled');
    }
  }

  Future<void> _pickVideo() async {
    AppLogger.info('Picking video from gallery');
    final pickedFile = await _picker.pickVideo(source: ImageSource.gallery);

    if (pickedFile != null) {
      AppLogger.info('Video picked: ${pickedFile.path}');
      _disposeVideoController();
      
      setState(() {
        _pickedFile = pickedFile;
        _image = kIsWeb ? null : File(pickedFile.path);
        _blurredImageUrl = null;
        _isVideo = true;
        _maskBytes = null;
      });
      
      _initializeVideoController(pickedFile);
    } else {
      AppLogger.info('Video picking cancelled');
    }
  }

  void _disposeVideoController() {
    _videoController?.dispose();
    _videoController = null;
  }

  Future<void> _initializeVideoController(XFile file) async {
    VideoPlayerController controller;
    if (kIsWeb) {
      controller = VideoPlayerController.networkUrl(Uri.parse(file.path));
    } else {
      controller = VideoPlayerController.file(File(file.path));
    }
    
    try {
      await controller.initialize();
      await controller.setLooping(true);
      await controller.play();
      if (mounted) {
        setState(() {
          _videoController = controller;
        });
      }
    } catch (e) {
      AppLogger.error('Error initializing video controller', e);
    }
  }

  Future<void> _handleBlur(String blurType) async {
    if (_pickedFile == null) return;

    // For video, force SAM2 shape
    final effectiveShape = _isVideo ? 'sam2' : _blurShape;

    AppLogger.info('Starting blur process. Type: $blurType, IsVideo: $_isVideo');
    setState(() => _isLoading = true);

    try {
      if (_isVideo) {
        final response = await _apiService.uploadVideo(
          videoFile: _pickedFile!,
          blurType: blurType,
          blurStrength: _blurStrength.round(),
          blurShape: effectiveShape,
          blurStyle: _blurStyle,
        );
        
        final jobId = response['job_id'];
        AppLogger.info('Video job started: $jobId');
        
        // Poll for status
        bool isDone = false;
        while (!isDone) {
          await Future.delayed(const Duration(seconds: 5));
          final status = await _apiService.checkVideoStatus(jobId);
          
          if (status['status'] == 'completed') {
            isDone = true;
            AppLogger.info('Video processing completed');
            if (mounted) {
               ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text('Video processed! Download at: ${AppConstants.baseUrl}${status['result_url']}'),
                  backgroundColor: Colors.green,
                  duration: const Duration(seconds: 10),
                  action: SnackBarAction(
                    label: 'Copy URL',
                    onPressed: () {
                      // TODO: Copy to clipboard or open
                    },
                  ),
                ),
              );
            }
          } else if (status['status'] == 'failed') {
            AppLogger.error('Video processing failed: ${status['error']}');
            throw Exception(status['error']);
          }
        }
      } else {
        final bytes = await _apiService.uploadAndBlur(
          pickedFile: _pickedFile,
          imageFile: _image,
          blurType: blurType,
          maskBytes: _maskBytes,
          blurStrength: _blurStrength.round(),
          blurShape: _blurShape,
          blurStyle: _blurStyle,
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
      }
    } catch (e, stack) {
      AppLogger.error('Error in _handleBlur', e, stack);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error: $e'),
            backgroundColor: AppTheme.error,
            behavior: SnackBarBehavior.floating,
          ),
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
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        title: const Text('BlurAI'),
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      body: Container(
        decoration: const BoxDecoration(
          gradient: RadialGradient(
            center: Alignment.topLeft,
            radius: 1.5,
            colors: [
              Color(0xFF1A1A2E),
              Color(0xFF0A0A0A),
            ],
          ),
        ),
        child: SafeArea(
          child: Column(
            children: [
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.all(20.0),
                  child: _buildMainContent(),
                ),
              ),
              _buildControlPanel(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildMainContent() {
    if (_isLoading) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const CircularProgressIndicator(color: AppTheme.primary),
            const SizedBox(height: 20),
            Text(
              "Processing AI Magic...",
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                color: Colors.white70,
              ),
            ).animate().fadeIn().shimmer(),
          ],
        ),
      );
    }

    if (_pickedFile == null && _image == null) {
      return Center(
        child: GlassContainer(
          width: double.infinity,
          height: 400,
          onTap: _pickImage,
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.add_photo_alternate_outlined,
                size: 64,
                color: AppTheme.primary.withOpacity(0.8),
              ).animate().scale(duration: 600.ms, curve: Curves.easeOutBack),
              const SizedBox(height: 20),
              Text(
                "Tap to Upload Image",
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 10),
              Text(
                "Supports JPG, PNG • Max 10MB",
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Colors.white54,
                ),
              ),
            ],
          ),
        ),
      ).animate().fadeIn(duration: 500.ms).slideY(begin: 0.1, end: 0);
    }

    return Center(
      child: GlassContainer(
        padding: EdgeInsets.zero,
        child: ClipRRect(
          borderRadius: BorderRadius.circular(24),
          child: Stack(
            fit: StackFit.expand,
            children: [
              if (_isVideo)
                if (_videoController != null && _videoController!.value.isInitialized)
                  AspectRatio(
                    aspectRatio: _videoController!.value.aspectRatio,
                    child: VideoPlayer(_videoController!),
                  )
                else
                  const Center(child: CircularProgressIndicator(color: Colors.white))
              else if (_blurredImageUrl != null)
                Image.network(_blurredImageUrl!, fit: BoxFit.contain)
              else if (kIsWeb && _pickedFile != null)
                Image.network(_pickedFile!.path, fit: BoxFit.contain)
              else if (_image != null && !_isVideo)
                Image.file(_image!, fit: BoxFit.contain)
              else
                const SizedBox(),
                
              // Mask Indicator Overlay
              if (_maskBytes != null && _blurredImageUrl == null && !_isVideo)
                Positioned(
                  top: 16,
                  right: 16,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: AppTheme.primary,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: const Row(
                      children: [
                        Icon(Icons.brush, size: 14, color: Colors.white),
                        SizedBox(width: 4),
                        Text(
                          "Mask Active",
                          style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                  ),
                ).animate().fadeIn().scale(),
            ],
          ),
        ),
      ),
    ).animate().fadeIn();
  }

  Widget _buildControlPanel() {
    return GlassContainer(
      padding: const EdgeInsets.all(20),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              _buildActionButton(
                icon: Icons.image,
                label: "Photo",
                onTap: _pickImage,
              ),
              _buildActionButton(
                icon: Icons.videocam,
                label: "Video",
                onTap: _pickVideo,
              ),
              if ((_pickedFile != null || _image != null) && !_isVideo)
                _buildActionButton(
                  icon: Icons.brush,
                  label: "Mask",
                  isActive: _maskBytes != null,
                  onTap: _openMaskEditor,
                ),
            ],
          ),
          if (_pickedFile != null || _image != null) ...[
            const SizedBox(height: 20),
            // Blur Settings
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  "Blur Strength: ${_blurStrength.round()}",
                  style: const TextStyle(color: Colors.white70, fontSize: 12),
                ),
                SliderTheme(
                  data: SliderTheme.of(context).copyWith(
                    activeTrackColor: AppTheme.primary,
                    inactiveTrackColor: Colors.white10,
                    thumbColor: Colors.white,
                    overlayColor: AppTheme.primary.withOpacity(0.2),
                  ),
                  child: Slider(
                    value: _blurStrength,
                    min: 1,
                    max: 100,
                    onChanged: (value) => setState(() => _blurStrength = value),
                  ),
                ),
                const SizedBox(height: 8),
                // Only show shape options for images, video uses SAM2 by default
                if (!_isVideo) ...[
                  Row(
                    children: [
                      const Text(
                        "Shape: ",
                        style: TextStyle(color: Colors.white70, fontSize: 12),
                      ),
                      const SizedBox(width: 10),
                      _buildShapeOption("Box", "rect"),
                      const SizedBox(width: 10),
                      _buildShapeOption("Oval", "oval"),
                      const SizedBox(width: 10),
                      _buildShapeOption("Trace", "trace"),
                      const SizedBox(width: 10),
                      _buildShapeOption("AI (SAM2)", "sam2"),
                    ],
                  ),
                  const SizedBox(height: 8),
                ],
                Row(
                  children: [
                    const Text(
                      "Style: ",
                      style: TextStyle(color: Colors.white70, fontSize: 12),
                    ),
                    const SizedBox(width: 10),
                    _buildStyleOption("Smooth", "smooth"),
                    const SizedBox(width: 10),
                    _buildStyleOption("Pixelate", "pixelate"),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 20),
            Row(
              children: [
                Expanded(
                  child: GlowingButton(
                    text: _maskBytes != null ? "Blur Mask" : "Blur BG",
                    icon: Icons.blur_on,
                    onPressed: () => _handleBlur('background'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: GlowingButton(
                    text: "Blur Faces",
                    icon: Icons.face,
                    isPrimary: false,
                    onPressed: () => _handleBlur('faces'),
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    ).animate().slideY(begin: 1, end: 0, duration: 600.ms, curve: Curves.easeOutExpo);
  }

  Widget _buildShapeOption(String label, String value) {
    final isSelected = _blurShape == value;
    return GestureDetector(
      onTap: () => setState(() => _blurShape = value),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: isSelected ? AppTheme.primary : Colors.white10,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isSelected ? AppTheme.primary : Colors.transparent,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: isSelected ? Colors.white : Colors.white60,
            fontSize: 12,
            fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
          ),
        ),
      ),
    );
  }

  Widget _buildStyleOption(String label, String value) {
    final isSelected = _blurStyle == value;
    return GestureDetector(
      onTap: () => setState(() => _blurStyle = value),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: isSelected ? AppTheme.primary : Colors.white10,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isSelected ? AppTheme.primary : Colors.transparent,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: isSelected ? Colors.white : Colors.white60,
            fontSize: 12,
            fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
          ),
        ),
      ),
    );
  }

  Widget _buildActionButton({
    required IconData icon,
    required String label,
    required VoidCallback onTap,
    bool isActive = false,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: isActive ? AppTheme.primary.withOpacity(0.2) : Colors.transparent,
          borderRadius: BorderRadius.circular(12),
          border: isActive ? Border.all(color: AppTheme.primary) : null,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              color: isActive ? AppTheme.primary : Colors.white70,
            ),
            const SizedBox(height: 4),
            Text(
              label,
              style: TextStyle(
                color: isActive ? AppTheme.primary : Colors.white70,
                fontSize: 12,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
