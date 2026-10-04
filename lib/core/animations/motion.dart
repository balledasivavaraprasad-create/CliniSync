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
  });

  final Widget child;

  /// Position in the stagger sequence.
  final int index;
  final Duration stagger;
  final Duration duration;
  final double offset;

  @override
  State<SectionReveal> createState() => _SectionRevealState();
}

class _SectionRevealState extends State<SectionReveal>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: widget.duration,
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
    final delay = widget.stagger * widget.index;
    if (delay == Duration.zero) {
      _controller.forward();
    } else {
      Future<void>.delayed(delay, () {
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
        duration: widget.duration,
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
    duration: widget.period,
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
      duration: duration,
      curve: Curves.easeOutCubic,
      builder: (BuildContext context, double v, Widget? _) {
        return builder(context, formatter?.call(v) ?? v.toStringAsFixed(0));
      },
    );
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
