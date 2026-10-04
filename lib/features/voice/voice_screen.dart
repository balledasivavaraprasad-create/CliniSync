import 'dart:async';
import 'dart:io';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';

import '../../core/animations/motion.dart';
import '../../core/models/clinical_memory.dart';
import '../../core/repositories/providers.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../shared/loading/states.dart';
import '../../shared/widgets/app_icons.dart';
import '../../shared/widgets/primitives.dart';
import '../state/feature_providers.dart';

/// Voice — plan §9.20.
///
/// Dictate a clinical note: a pulsing filled-green mic, timer, animated
/// waveform, then an editable transcript with an
/// `AI transcript · review before use` pill. Extracted facts arrive as
/// `Needs verification` (that is the backend's own behaviour).
class VoiceScreen extends ConsumerStatefulWidget {
  const VoiceScreen({super.key, required this.patientId});

  final String patientId;

  @override
  ConsumerState<VoiceScreen> createState() => _VoiceScreenState();
}

class _VoiceScreenState extends ConsumerState<VoiceScreen>
    with SingleTickerProviderStateMixin {
  final AudioRecorder _recorder = AudioRecorder();
  final TextEditingController _transcript = TextEditingController();

  late final AnimationController _pulse = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1400),
  );

  bool _recording = false;
  bool _busy = false;
  bool _permissionDenied = false;
  Duration _elapsed = Duration.zero;
  final math.Random _random = math.Random();

  /// Animated bars for the waveform (deterministic per frame while recording).
  final List<double> _bars = List<double>.filled(28, 0.2);
  Timer? _tick;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _askPermission());
  }

  @override
  void dispose() {
    _tick?.cancel();
    _pulse.dispose();
    _recorder.dispose();
    _transcript.dispose();
    super.dispose();
  }

  Future<void> _askPermission() async {
    final PermissionStatus status = await Permission.microphone.request();
    if (!mounted) return;
    if (!status.isGranted) setState(() => _permissionDenied = true);
  }

  Future<void> _start() async {
    try {
      if (!await _recorder.hasPermission()) {
        if (mounted) setState(() => _permissionDenied = true);
        return;
      }
      final Directory dir = await getTemporaryDirectory();
      final String path =
          '${dir.path}/clinsync_note_${DateTime.now().millisecondsSinceEpoch}.m4a';
      await _recorder.start(
        const RecordConfig(encoder: AudioEncoder.aacLc),
        path: path,
      );
      if (!mounted) return;
      setState(() {
        _recording = true;
        _elapsed = Duration.zero;
      });
      _pulse.repeat(reverse: true);
      _tick = Timer.periodic(const Duration(milliseconds: 110), (_) {
        if (!mounted) return;
        setState(() {
          _elapsed += const Duration(milliseconds: 110);
          for (int i = 0; i < _bars.length; i++) {
            _bars[i] = 0.2 + _random.nextDouble() * 0.8;
          }
        });
      });
    } catch (_) {
      if (mounted) {
        AppSnack.error(context, 'Recording could not start on this device.');
      }
    }
  }

  Future<void> _stop() async {
    _tick?.cancel();
    _pulse.stop();
    final String? path = await _recorder.stop();
    if (!mounted) return;
    setState(() => _recording = false);
    if (path == null) return;

    setState(() => _busy = true);
    try {
      final note = await ref
          .read(voiceRepositoryProvider)
          .upload(widget.patientId, File(path));
      if (!mounted) return;
      _transcript.text = note.transcript;
      await showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        backgroundColor: AppColors.bgCanvas,
        builder: (BuildContext sheetContext) => _TranscriptSheet(
          patientId: widget.patientId,
          controller: _transcript,
          initial: note,
        ),
      );
    } catch (_) {
      if (mounted) {
        AppSnack.error(context, 'We couldn\'t transcribe that recording.');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_permissionDenied) {
      return Scaffold(
        backgroundColor: AppColors.bgCanvas,
        body: SafeArea(
          child: Column(
            children: <Widget>[
              TopBar(title: 'Voice note', onLeadingTap: () => context.pop()),
              Expanded(
                child: ErrorStateView(
                  title: 'Microphone access is off',
                  message:
                      'Allow microphone access to dictate a clinical note.',
                  retryLabel: 'Try again',
                  onRetry: _askPermission,
                ),
              ),
              const Padding(
                padding: EdgeInsets.all(AppSpacing.screenH),
                child: PrimaryPillButton(
                  label: 'Open settings',
                  icon: 'settings',
                  onPressed: openAppSettings,
                ),
              ),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      backgroundColor: AppColors.bgCanvas,
      body: SafeArea(
        child: Column(
          children: <Widget>[
            TopBar(
              title: 'Voice note',
              subtitle: _recording ? 'Recording…' : 'Not recording',
              onLeadingTap: () => context.pop(),
            ),
            Expanded(
              child: SingleChildScrollView(
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.screenH),
                  child: Column(
                    children: <Widget>[
                      const SizedBox(height: AppSpacing.xl),
                      // Serif prompt
                      Text(
                        'Dictate a clinical note',
                        style: AppTypography.titlePage,
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        'The transcript is linked to this patient and its facts stay flagged as needing verification.',
                        style: AppTypography.body
                            .copyWith(color: AppColors.textSecondary),
                        textAlign: TextAlign.center,
                      ),

                      const SizedBox(height: AppSpacing.xxl),

                      // Pulsing filled-green mic
                      _MicButton(
                        recording: _recording,
                        pulse: _pulse,
                        onTap: _recording ? _stop : (_busy ? null : _start),
                      ),

                      const SizedBox(height: AppSpacing.lg),

                      // Timer
                      Text(
                        _format(_elapsed),
                        style: AppTypography.numberLargeSans
                            .copyWith(fontSize: 28),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        _recording ? 'Tap to stop' : 'Tap to start recording',
                        style: AppTypography.caption,
                      ),

                      const SizedBox(height: AppSpacing.lg),

                      // Waveform
                      _Waveform(bars: _bars, active: _recording),

                      if (_busy) ...<Widget>[
                        const SizedBox(height: AppSpacing.lg),
                        const ClinNoticeBanner(
                          message: 'Transcribing and extracting facts…',
                          icon: 'loader',
                          tone: ClinNoticeTone.primary,
                        ),
                      ],

                      const SizedBox(height: AppSpacing.xl),
                      const ClinicalDisclaimer(),
                      const SizedBox(height: AppSpacing.xxl),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  static String _format(Duration d) {
    final String m = d.inMinutes.toString().padLeft(2, '0');
    final String s = (d.inSeconds % 60).toString().padLeft(2, '0');
    return '$m:$s';
  }
}

class _MicButton extends StatelessWidget {
  const _MicButton(
      {required this.recording, required this.pulse, required this.onTap});

  final bool recording;
  final AnimationController pulse;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final Widget core = Container(
      width: 108,
      height: 108,
      decoration:
          const BoxDecoration(color: AppColors.primary, shape: BoxShape.circle),
      alignment: Alignment.center,
      child: Icon(
        AppIcons.byName(recording ? 'square' : 'mic'),
        size: 40,
        color: AppColors.onPrimary,
      ),
    );

    return PressScale(
      onTap: onTap,
      child: AnimatedBuilder(
        animation: pulse,
        builder: (BuildContext context, Widget? child) {
          final double t = pulse.value;
          return Stack(
            alignment: Alignment.center,
            children: <Widget>[
              if (recording)
                Transform.scale(
                  scale: 1.0 + t * 0.22,
                  child: Container(
                    width: 108,
                    height: 108,
                    decoration: BoxDecoration(
                      color:
                          AppColors.primary.withValues(alpha: 0.18 * (1 - t)),
                      shape: BoxShape.circle,
                    ),
                  ),
                ),
              child!,
            ],
          );
        },
        child: core,
      ),
    );
  }
}

class _Waveform extends StatelessWidget {
  const _Waveform({required this.bars, required this.active});

  final List<double> bars;
  final bool active;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 48,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: <Widget>[
          for (final double b in bars)
            Container(
              width: 4,
              height: active ? 48 * b : 6,
              margin: const EdgeInsets.symmetric(horizontal: 1.5),
              decoration: BoxDecoration(
                color: active ? AppColors.primary : AppColors.dividerStrong,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
        ],
      ),
    );
  }
}

/// Transcript review — plan §9.20.
class _TranscriptSheet extends ConsumerStatefulWidget {
  const _TranscriptSheet({
    required this.patientId,
    required this.controller,
    required this.initial,
  });

  final String patientId;
  final TextEditingController controller;
  final VoiceNote initial;

  @override
  ConsumerState<_TranscriptSheet> createState() => _TranscriptSheetState();
}

class _TranscriptSheetState extends ConsumerState<_TranscriptSheet> {
  bool _saving = false;

  @override
  Widget build(BuildContext context) {
    final VoiceNote note = widget.initial;

    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: SafeArea(
        top: false,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            const SizedBox(height: AppSpacing.sm),
            Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: AppColors.dividerStrong,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.screenH,
                AppSpacing.md,
                AppSpacing.screenH,
                AppSpacing.sm,
              ),
              child: Row(
                children: <Widget>[
                  Expanded(
                    child: Text('Review transcript',
                        style: AppTypography.titleScreen),
                  ),
                  CircleIconButton(
                    icon: 'x',
                    size: 38,
                    iconSize: 17,
                    onTap: () => Navigator.of(context).maybePop(),
                  ),
                ],
              ),
            ),
            Flexible(
              child: SingleChildScrollView(
                padding:
                    const EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: <Widget>[
                    if (note.usedFallback)
                      const ClinNoticeBanner(
                        message:
                            'Transcription was unavailable, so only the audio placeholder was stored. '
                            'Type the note below instead.',
                        tone: ClinNoticeTone.warning,
                        icon: 'alertTriangle',
                      )
                    else
                      const ClinNoticeBanner(
                        message: 'AI transcript · review before use',
                        tone: ClinNoticeTone.primary,
                        icon: 'sparkles',
                      ),
                    const SizedBox(height: AppSpacing.sm),
                    TextField(
                      controller: widget.controller,
                      maxLines: 6,
                      minLines: 4,
                      style: AppTypography.body,
                      cursorColor: AppColors.primary,
                      decoration: const InputDecoration(
                        hintText: 'Type or edit the clinical note…',
                      ),
                    ),
                    const SizedBox(height: AppSpacing.md),
                    if (note.proposedFacts.isNotEmpty) ...<Widget>[
                      Text('FACTS EXTRACTED',
                          style: AppTypography.capsLabel.copyWith(
                            color: AppColors.textSecondary,
                            fontSize: 10,
                          )),
                      const SizedBox(height: AppSpacing.xs),
                      for (final VoiceProposedFact f in note.proposedFacts)
                        Padding(
                          padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                          child: SurfaceCard(
                            padding: const EdgeInsets.all(AppSpacing.sm),
                            child: Row(
                              children: <Widget>[
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: <Widget>[
                                      Text(
                                        f.value,
                                        style: AppTypography.bodyStrong
                                            .copyWith(fontSize: 13),
                                      ),
                                      Text(
                                        f.factType.label,
                                        style: AppTypography.bodyBullet
                                            .copyWith(fontSize: 11),
                                      ),
                                    ],
                                  ),
                                ),
                                const StatusPill(
                                  label: 'Needs verification',
                                  variant: StatusPillVariant.needsReview,
                                  dense: true,
                                ),
                              ],
                            ),
                          ),
                        ),
                      const SizedBox(height: AppSpacing.sm),
                    ],
                    const ClinicalDisclaimer(),
                    const SizedBox(height: AppSpacing.md),
                    Row(
                      children: <Widget>[
                        Expanded(
                          child: SizedBox(
                            height: 48,
                            child: PressScale(
                              onTap: () => Navigator.of(context).maybePop(),
                              child: Container(
                                decoration: BoxDecoration(
                                  color: AppColors.surfaceTint,
                                  borderRadius:
                                      BorderRadius.circular(AppSpacing.xxl),
                                ),
                                alignment: Alignment.center,
                                child: Text(
                                  'Discard',
                                  style: AppTypography.bodyStrong
                                      .copyWith(fontSize: 14),
                                ),
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(width: AppSpacing.xs),
                        Expanded(
                          child: SizedBox(
                            height: 48,
                            child: PressScale(
                              onTap: _saving ? null : () => _save(note),
                              child: Container(
                                decoration: BoxDecoration(
                                  color: AppColors.primary,
                                  borderRadius:
                                      BorderRadius.circular(AppSpacing.xxl),
                                ),
                                alignment: Alignment.center,
                                child: Text(
                                  _saving ? 'Saving…' : 'Save',
                                  style: AppTypography.button
                                      .copyWith(fontSize: 14),
                                ),
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.sm),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _save(VoiceNote note) async {
    setState(() => _saving = true);
    try {
      await ref
          .read(voiceRepositoryProvider)
          .review(note.id, editedTranscript: widget.controller.text);
      if (!mounted) return;
      Navigator.of(context).pop();
      AppSnack.show(context, 'Note saved and linked to this patient');
      ref.invalidate(factsProvider(widget.patientId));
    } catch (_) {
      if (mounted) {
        setState(() => _saving = false);
        AppSnack.error(context, 'Could not save that note. Try again.');
      }
    }
  }
}
