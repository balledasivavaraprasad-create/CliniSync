import 'dart:async';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';

import '../../core/constants/app_assets.dart';
import '../../core/theme/app_colors.dart';

/// Ambient video layer — plan §7.8.
///
/// * Muted, looping, `BoxFit.cover`, no controls.
/// * The poster still is always painted underneath, so first paint is instant
///   and the video failing / initialising slowly degrades silently.
/// * Disabled entirely when `MediaQuery.disableAnimations` is set.
/// * The controller is disposed on leaving and paused when the app is
///   backgrounded.
/// * **Web is excluded**: `video_player` renders through a platform view there,
///   and a platform view always composites *above* the Flutter canvas, which
///   would paint the hero over the search pill that sits below it. On web the
///   poster still is used alone. Logged in `docs/frontend/DECISIONS.md`.
class AmbientVideo extends StatefulWidget {
  const AmbientVideo({
    super.key,
    required this.assetPath,
    this.fit = BoxFit.cover,
    this.opacity = 1,
  });

  final String assetPath;
  final BoxFit fit;
  final double opacity;

  @override
  State<AmbientVideo> createState() => _AmbientVideoState();
}

class _AmbientVideoState extends State<AmbientVideo>
    with WidgetsBindingObserver {
  VideoPlayerController? _controller;
  bool _ready = false;
  bool _failed = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    final bool reduce = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    if (!reduce) unawaited(_init());
  }

  Future<void> _init() async {
    try {
      final VideoPlayerController controller =
          VideoPlayerController.asset(widget.assetPath);
      await controller.initialize();
      await controller.setLooping(true);
      await controller.setVolume(0);
      await controller.play();
      if (!mounted) {
        await controller.dispose();
        return;
      }
      setState(() {
        _controller = controller;
        _ready = true;
      });
    } catch (_) {
      // Poster fallback stays visible; no error is surfaced to the user.
      if (mounted) setState(() => _failed = true);
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final VideoPlayerController? controller = _controller;
    if (controller == null || !_ready) return;
    if (state == AppLifecycleState.resumed) {
      unawaited(controller.play());
    } else if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused ||
        state == AppLifecycleState.detached ||
        state == AppLifecycleState.hidden) {
      unawaited(controller.pause());
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    unawaited(_controller?.dispose());
    _controller = null;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_failed || !_ready || _controller == null) {
      return const SizedBox.shrink();
    }
    return Opacity(
      opacity: widget.opacity,
      child: FittedBox(
        fit: widget.fit,
        clipBehavior: Clip.hardEdge,
        child: SizedBox(
          width: _controller!.value.size.width,
          height: _controller!.value.size.height,
          child: VideoPlayer(_controller!),
        ),
      ),
    );
  }
}

/// `AmbientBackground` with the video wired in — the poster always paints first.
class AmbientLayer extends StatelessWidget {
  const AmbientLayer({
    super.key,
    this.height = 0,
    this.videoAsset = AppAssets.heroVideo,
    this.posterAsset = AppAssets.heroPoster,
    this.washOpacity = 0.45,
    this.videoOpacity = 1,
    this.videoFraction = 1,
    this.overlay,
    this.fit = BoxFit.cover,
  });

  /// Only used when the layer is not placed in a `Positioned.fill`.
  final double height;
  final String? videoAsset;
  final String? posterAsset;
  final double washOpacity;

  /// The video sits *under* a strong wash, so it contributes motion and depth
  /// rather than competing with the headline.
  final double videoOpacity;

  /// Fraction of the layer's height the video may occupy, anchored to the top.
  /// Keeping it below 1 stops a platform-view video from reaching content that
  /// sits directly beneath the layer.
  final double videoFraction;
  final Widget? overlay;
  final BoxFit fit;

  @override
  Widget build(BuildContext context) {
    final bool reduce = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    final bool showVideo = !reduce && videoAsset != null && !kIsWeb;
    final double fraction = videoFraction.clamp(0.05, 1.0);

    return SizedBox(
      height: height,
      width: double.infinity,
      child: Stack(
        fit: StackFit.expand,
        children: <Widget>[
          if (posterAsset != null)
            Image.asset(posterAsset!,
                fit: fit, errorBuilder: (_, __, ___) => const _PosterFallback())
          else
            const _PosterFallback(),
          if (showVideo)
            Align(
              alignment: Alignment.topCenter,
              child: SizedBox(
                height: height * fraction,
                width: double.infinity,
                child: ClipRect(
                  child: AmbientVideo(
                    assetPath: videoAsset!,
                    fit: fit,
                    opacity: videoOpacity,
                  ),
                ),
              ),
            ),
          IgnorePointer(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: <Color>[
                    AppColors.bgCanvas.withValues(alpha: washOpacity * 0.7),
                    AppColors.bgCanvas.withValues(alpha: washOpacity),
                    AppColors.bgCanvas.withValues(alpha: washOpacity * 0.3),
                  ],
                  stops: const <double>[0, 0.5, 1],
                ),
              ),
            ),
          ),
          if (overlay != null) overlay!,
        ],
      ),
    );
  }
}

/// A very subtle ambient wash for the Brief and Approval headers — plan §7.8.
class AmbientRibbon extends StatelessWidget {
  const AmbientRibbon({
    super.key,
    this.height = 120,
    this.videoAsset = AppAssets.ribbonVideo,
    this.posterAsset = AppAssets.ribbonPoster,
    this.opacity = 0.3,
  });

  /// Only used when the layer is not placed in a `Positioned.fill`.
  final double height;
  final String? videoAsset;
  final String? posterAsset;
  final double opacity;

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: Opacity(
        opacity: opacity,
        child: SizedBox(
          height: height,
          child: AmbientLayer(
            height: height,
            videoAsset: videoAsset,
            posterAsset: posterAsset,
            washOpacity: 0.55,
            videoOpacity: 0.35,
            videoFraction: 0.62,
          ),
        ),
      ),
    );
  }
}

class _PosterFallback extends StatelessWidget {
  const _PosterFallback();

  @override
  Widget build(BuildContext context) =>
      const ColoredBox(color: AppColors.primarySoft);
}
