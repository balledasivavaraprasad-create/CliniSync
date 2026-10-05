import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

/// Section reveal — fade + 12 px translate, 280 ms, 40 ms stagger, once per
/// screen build (plan §7.9). Respects `MediaQuery.disableAnimations`.
class SectionReveal extends StatefulWidget {
  const SectionReveal({
    super.key,
    required this.child,
    this.index = 0,
    this.stagger = const Duration(milliseconds: 40),
    this.duration = const Duration(milliseconds: 280),
    this.offset = 12,
    this.delay = Duration.zero,
  });

  final Widget child;

  /// Position in the stagger sequence.
  final int index;
  final Duration stagger;
  final Duration duration;
  final double offset;

  /// Extra hold-off before this section reveals — used to let a headline
  /// animation finish before the copy below it starts.
  final Duration delay;

  @override
  State<SectionReveal> createState() => _SectionRevealState();
}

class _SectionRevealState extends State<SectionReveal>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: _scaled(widget.duration),
  );

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _play());
  }

  void _play() {
    if (!mounted) return;
    final reduce = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    if (reduce) {
      _controller.value = 1;
      return;
    }
    final Duration wait =
        _scaled(widget.delay + widget.stagger * widget.index);
    if (wait == Duration.zero) {
      _controller.forward();
    } else {
      Future<void>.delayed(wait, () {
        if (mounted) _controller.forward();
      });
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final reduce = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    if (reduce) return widget.child;
    final curve =
        CurvedAnimation(parent: _controller, curve: Curves.easeOutCubic);
    return AnimatedBuilder(
      animation: curve,
      builder: (BuildContext context, Widget? child) {
        return Opacity(
          opacity: curve.value.clamp(0.0, 1.0),
          child: Transform.translate(
            offset: Offset(0, widget.offset * (1 - curve.value)),
            child: child,
          ),
        );
      },
      child: widget.child,
    );
  }
}

/// QA multiplier for every duration in this file, as a percentage.
///
/// Defaults to 100 (no scaling). Build with
/// `--dart-define=CLINSYNC_MOTION_SCALE=800` to slow all motion down enough to
/// screenshot mid-animation (`tools/capture_hero_frames.py`); production builds
/// never set it.
///
/// Declared as an `int` percentage rather than a `double` because
/// `double.fromEnvironment` is not a constant expression on this SDK.
const int _motionScalePercent =
    int.fromEnvironment('CLINSYNC_MOTION_SCALE', defaultValue: 100);

const double _motionScale =
    _motionScalePercent <= 0 ? 1.0 : _motionScalePercent / 100.0;

/// [duration] scaled by the QA motion multiplier.
Duration _scaled(Duration duration) => Duration(
      microseconds: (duration.inMicroseconds * _motionScale).round(),
    );

/// Reveals a list of children with a per-index stagger.
class StaggeredColumn extends StatelessWidget {
  const StaggeredColumn({
    super.key,
    required this.children,
    this.stagger = const Duration(milliseconds: 40),
    this.duration = const Duration(milliseconds: 280),
    this.spacing = 0,
  });

  final List<Widget> children;
  final Duration stagger;
  final Duration duration;
  final double spacing;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        for (int i = 0; i < children.length; i++) ...<Widget>[
          SectionReveal(
            index: i,
            stagger: stagger,
            duration: duration,
            child: children[i],
          ),
          if (i < children.length - 1 && spacing > 0) SizedBox(height: spacing),
        ],
      ],
    );
  }
}

/// Press feedback: scale 0.98, 120 ms (plan §7.9).
class PressScale extends StatefulWidget {
  const PressScale({
    super.key,
    required this.child,
    this.onTap,
    this.onLongPress,
    this.scale = 0.98,
    this.duration = const Duration(milliseconds: 120),
    this.behaviour = HitTestBehavior.opaque,
  });

  final Widget child;
  final VoidCallback? onTap;
  final VoidCallback? onLongPress;
  final double scale;
  final Duration duration;
  final HitTestBehavior behaviour;

  @override
  State<PressScale> createState() => _PressScaleState();
}

class _PressScaleState extends State<PressScale> {
  bool _down = false;

  void _set(bool v) {
    if (_down != v && mounted) setState(() => _down = v);
  }

  @override
  Widget build(BuildContext context) {
    final reduce = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    Widget content = widget.child;
    if (!reduce) {
      content = AnimatedScale(
        scale: _down ? widget.scale : 1,
        duration: _scaled(widget.duration),
        curve: Curves.easeOut,
        child: content,
      );
    }
    if (widget.onTap == null && widget.onLongPress == null) return content;
    return GestureDetector(
      behavior: widget.behaviour,
      onTapDown: (_) => _set(true),
      onTapUp: (_) => _set(false),
      onTapCancel: () => _set(false),
      onTap: widget.onTap,
      onLongPress: widget.onLongPress,
      child: content,
    );
  }
}

/// Active processing node pulses softly (1.0 → 1.08, 900 ms loop) — plan §7.9.
class SoftPulse extends StatefulWidget {
  const SoftPulse({
    super.key,
    required this.child,
    this.from = 1.0,
    this.to = 1.08,
    this.period = const Duration(milliseconds: 900),
    this.active = true,
  });

  final Widget child;
  final double from;
  final double to;
  final Duration period;
  final bool active;

  @override
  State<SoftPulse> createState() => _SoftPulseState();
}

class _SoftPulseState extends State<SoftPulse>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: _scaled(widget.period),
  );

  @override
  void initState() {
    super.initState();
    if (widget.active) _controller.repeat(reverse: true);
  }

  @override
  void didUpdateWidget(SoftPulse old) {
    super.didUpdateWidget(old);
    if (widget.active && !_controller.isAnimating) {
      _controller.repeat(reverse: true);
    } else if (!widget.active && _controller.isAnimating) {
      _controller.stop();
      _controller.value = 0;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final reduce = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    if (!widget.active || reduce) return widget.child;
    final curved =
        CurvedAnimation(parent: _controller, curve: Curves.easeInOut);
    return AnimatedBuilder(
      animation: curved,
      builder: (BuildContext context, Widget? child) {
        final t = curved.value;
        return Transform.scale(
            scale: widget.from + (widget.to - widget.from) * t, child: child);
      },
      child: widget.child,
    );
  }
}

/// Hero parallax, ≤ 0.25 factor, Home only (plan §7.9).
class AmbientParallax extends StatefulWidget {
  const AmbientParallax({
    super.key,
    required this.child,
    this.factor = 0.18,
    this.maxShift = 26,
  });

  final Widget child;
  final double factor;
  final double maxShift;

  @override
  State<AmbientParallax> createState() => _AmbientParallaxState();
}

class _AmbientParallaxState extends State<AmbientParallax> {
  double _dy = 0;

  @override
  Widget build(BuildContext context) {
    final reduce = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    if (reduce) return widget.child;
    final factor = widget.factor.clamp(0.0, 0.25);
    return NotificationListener<ScrollNotification>(
      onNotification: (ScrollNotification n) {
        if (n.metrics.axis != Axis.vertical) return false;
        final next = (-n.metrics.pixels * factor)
            .clamp(-widget.maxShift, widget.maxShift);
        if ((next - _dy).abs() > 0.4) setState(() => _dy = next);
        return false;
      },
      child: Transform.translate(offset: Offset(0, _dy), child: widget.child),
    );
  }
}

/// Counts a number from 0 → value over 700 ms `easeOutCubic` (plan §7.9).
class AnimatedCount extends StatelessWidget {
  const AnimatedCount({
    super.key,
    required this.value,
    required this.builder,
    this.duration = const Duration(milliseconds: 700),
    this.formatter,
  });

  final double value;
  final Duration duration;
  final String Function(double value)? formatter;
  final Widget Function(BuildContext context, String display) builder;

  @override
  Widget build(BuildContext context) {
    final reduce = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    if (reduce) {
      return builder(
          context, formatter?.call(value) ?? value.toStringAsFixed(0));
    }
    return TweenAnimationBuilder<double>(
      tween: Tween<double>(begin: 0, end: value),
      duration: _scaled(duration),
      curve: Curves.easeOutCubic,
      builder: (BuildContext context, double v, Widget? _) {
        return builder(context, formatter?.call(v) ?? v.toStringAsFixed(0));
      },
    );
  }
}

/// The landing page's hero-title reveal, line by line.
///
/// `index.html:145-149` + `assets/css/style.css:290-295`:
/// ```css
/// .hero__title .line    { display:block; overflow:hidden; padding-block:.06em }
/// .hero__title .line__in{ display:inline-block; transform:translateY(115%);
///                        transition:transform 1.1s var(--ease-out) }
/// .is-ready .hero__title .line__in { transform:translateY(0) }
/// .hero__title .line:nth-child(2) .line__in { transition-delay:.09s }
/// .hero__title .line:nth-child(3) .line__in { transition-delay:.18s }
/// ```
///
/// Each line is clipped by its own box and the text starts one line-height
/// below it, so the glyphs appear to be wiped upward rather than faded. The
/// landing page uses `--ease-out: cubic-bezier(.16,1,.3,1)`, which is exactly
/// Flutter's [Curves.easeOutExpo].
///
/// Trigger is a post-frame callback — the landing page's equivalent is the
/// `is-ready` class the preloader adds. Plays once per mount and short-circuits
/// to the finished state under `MediaQuery.disableAnimations`.
class LineReveal extends StatefulWidget {
  const LineReveal({
    super.key,
    required this.lines,
    required this.lineHeight,
    this.duration = const Duration(milliseconds: 1100),
    this.stagger = const Duration(milliseconds: 90),
    this.startOffset = 1.15,
    this.clipPadding = const EdgeInsets.symmetric(vertical: 0.06),
  });

  /// One entry per line, already styled by the caller. Each must be a single
  /// line of text at [lineHeight].
  final List<Widget> lines;

  /// Height of one line, in logical pixels — normally
  /// `fontSize × TextStyle.height` from the caller's style. Passed explicitly
  /// because the reveal translates by a percentage of the line box and cannot
  /// know the box height before layout.
  final double lineHeight;

  final Duration duration;
  final Duration stagger;

  /// Fraction of [lineHeight] the text starts below its clip. The landing page
  /// uses `translateY(115%)`.
  final double startOffset;

  /// Padding inside the clip box, so ascenders/descenders are not shaved.
  final EdgeInsets clipPadding;

  @override
  State<LineReveal> createState() => _LineRevealState();
}

class _LineRevealState extends State<LineReveal>
    with SingleTickerProviderStateMixin {
  /// The controller spans every line's delay **and** its own ramp, so line *n*
  /// finishes `stagger × n` later than line 0 — a true stagger rather than
  /// three ramps that all end together.
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: _scaled(widget.duration +
        widget.stagger * (widget.lines.isEmpty ? 0 : widget.lines.length - 1)),
  );

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _play());
  }

  void _play() {
    if (!mounted) return;
    if (MediaQuery.maybeOf(context)?.disableAnimations ?? false) {
      _controller.value = 1;
      return;
    }
    _controller.forward();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (MediaQuery.maybeOf(context)?.disableAnimations ?? false) {
      return _lines(1);
    }
    return AnimatedBuilder(
      animation: _controller,
      builder: (BuildContext context, Widget? _) => _lines(_controller.value),
    );
  }

  Widget _lines(double t) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        for (int i = 0; i < widget.lines.length; i++)
          ClipRect(
            child: SizedBox(
              height: widget.lineHeight + widget.clipPadding.vertical,
              child: OverflowBox(
                alignment: Alignment.topLeft,
                minHeight: 0,
                maxHeight: double.infinity,
                child: Transform.translate(
                  offset: Offset(0, _lineOffset(t, i)),
                  child: widget.lines[i],
                ),
              ),
            ),
          ),
      ],
    );
  }

  /// Scaled per-line ramp and per-line delay, in microseconds.
  ///
  /// These must be the *scaled* values, not `widget.duration`/`widget.stagger`:
  /// `t` is progress through the scaled controller, so dividing it by an
  /// unscaled duration would saturate the ramp almost immediately and the lines
  /// would appear to jump straight to their final position.
  late final int _lineUs = _scaled(widget.duration).inMicroseconds;
  late final int _staggerUs = _scaled(widget.stagger).inMicroseconds;

  /// How far line [index] still sits below its clip box, in logical pixels.
  double _lineOffset(double t, int index) {
    final double nowUs = t * _controller.duration!.inMicroseconds;
    final double local = ((nowUs - _staggerUs * index) / _lineUs).clamp(0.0, 1.0);
    return widget.startOffset *
        widget.lineHeight *
        (1 - Curves.easeOutExpo.transform(local));
  }
}

/// Soft fade used on top of imagery to hold text contrast at AA.
class AmbientScrim extends StatelessWidget {
  const AmbientScrim({
    super.key,
    required this.child,
    this.opacity = 0.42,
    this.color,
  });

  final Widget child;
  final double opacity;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    return Stack(
      fit: StackFit.expand,
      children: <Widget>[
        child,
        IgnorePointer(
          child: Container(
            color: (color ?? AppColors.bgCanvas).withValues(alpha: opacity),
          ),
        ),
      ],
    );
  }
}
