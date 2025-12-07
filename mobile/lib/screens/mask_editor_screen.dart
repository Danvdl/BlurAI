import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

class MaskEditorScreen extends StatefulWidget {
  final XFile imageFile;

  const MaskEditorScreen({super.key, required this.imageFile});

  @override
  State<MaskEditorScreen> createState() => _MaskEditorScreenState();
}

class _MaskEditorScreenState extends State<MaskEditorScreen> {
  List<List<Offset>> _strokes = [];
  List<Offset> _currentStroke = [];
  double _brushSize = 20.0;

  void _startStroke(DragStartDetails details) {
    setState(() {
      _currentStroke = [details.localPosition];
      _strokes.add(_currentStroke);
    });
  }

  void _updateStroke(DragUpdateDetails details) {
    setState(() {
      _currentStroke.add(details.localPosition);
      // We need to update the last stroke in the list
      _strokes.last = List.from(_currentStroke);
    });
  }

  void _endStroke(DragEndDetails details) {
    // Stroke finished
  }

  void _undo() {
    if (_strokes.isNotEmpty) {
      setState(() {
        _strokes.removeLast();
      });
    }
  }

  void _clear() {
    setState(() {
      _strokes.clear();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Edit Mask'),
        actions: [
          IconButton(
            icon: const Icon(Icons.undo),
            onPressed: _strokes.isNotEmpty ? _undo : null,
          ),
          IconButton(
            icon: const Icon(Icons.check),
            onPressed: () {
              // TODO: Return the mask data
              Navigator.pop(context);
            },
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: LayoutBuilder(
              builder: (context, constraints) {
                return Stack(
                  children: [
                    // Background Image
                    Positioned.fill(
                      child: kIsWeb
                          ? Image.network(
                              widget.imageFile.path,
                              fit: BoxFit.contain,
                            )
                          : Image.file(
                              File(widget.imageFile.path),
                              fit: BoxFit.contain,
                            ),
                    ),
                    // Drawing Layer
                    Positioned.fill(
                      child: GestureDetector(
                        onPanStart: _startStroke,
                        onPanUpdate: _updateStroke,
                        onPanEnd: _endStroke,
                        child: CustomPaint(
                          painter: MaskPainter(
                            strokes: _strokes,
                            brushSize: _brushSize,
                          ),
                          size: Size.infinite,
                        ),
                      ),
                    ),
                  ],
                );
              },
            ),
          ),
          // Tools Panel
          Container(
            padding: const EdgeInsets.all(16.0),
            color: Colors.grey[200],
            child: Row(
              children: [
                const Text('Brush Size:'),
                Expanded(
                  child: Slider(
                    value: _brushSize,
                    min: 5.0,
                    max: 50.0,
                    onChanged: (value) {
                      setState(() {
                        _brushSize = value;
                      });
                    },
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.delete),
                  onPressed: _clear,
                  tooltip: 'Clear All',
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class MaskPainter extends CustomPainter {
  final List<List<Offset>> strokes;
  final double brushSize;

  MaskPainter({required this.strokes, required this.brushSize});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.red.withOpacity(0.5)
      ..strokeCap = StrokeCap.round
      ..strokeWidth = brushSize
      ..style = PaintingStyle.stroke;

    for (final stroke in strokes) {
      if (stroke.isEmpty) continue;
      
      final path = Path();
      path.moveTo(stroke.first.dx, stroke.first.dy);
      
      for (int i = 1; i < stroke.length; i++) {
        path.lineTo(stroke[i].dx, stroke[i].dy);
      }
      
      canvas.drawPath(path, paint);
    }
  }

  @override
  bool shouldRepaint(covariant MaskPainter oldDelegate) {
    return true;
  }
}
