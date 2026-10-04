import 'dart:io';

import 'package:clinicsync/core/config/app_config.dart';
import 'package:clinicsync/core/constants/enums.dart';
import 'package:clinicsync/core/networking/error_messages.dart';
import 'package:clinicsync/core/theme/app_colors.dart';
import 'package:clinicsync/core/theme/app_radii.dart';
import 'package:clinicsync/core/theme/app_spacing.dart';
import 'package:clinicsync/core/theme/app_theme.dart';
import 'package:clinicsync/core/theme/app_typography.dart';
import 'package:clinicsync/core/utils/confidence_band.dart';
import 'package:clinicsync/core/utils/date_format.dart';
import 'package:clinicsync/shared/widgets/app_icons.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('§7.1 colour tokens', () {
    test('the single accent is the sampled sage green', () {
      expect(AppColors.primary, const Color(0xFF527A55));
      expect(AppColors.bgCanvas, const Color(0xFFF6F6F4));
      expect(AppColors.surface, const Color(0xFFFFFFFF));
    });

    test('contrast of white text on the primary fill is at least AA', () {
      double luminance(Color c) => c.computeLuminance();
      final double l1 = luminance(AppColors.primary);
      final double l2 = luminance(AppColors.onPrimary);
      final double ratio = (l1 > l2 ? (l1 + 0.05) / (l2 + 0.05) : (l2 + 0.05) / (l1 + 0.05));
      expect(ratio, greaterThanOrEqualTo(4.5));
    });

    test('the headline black and the accent green differ', () {
      expect(AppColors.textPrimary, isNot(AppColors.primary));
    });
  });

  group('§7.2 typography', () {
    test('the serif and sans families are the bundled ones', () {
      expect(AppFont.serif, 'CormorantGaramond');
      expect(AppFont.sans, 'Inter');
      expect(AppTypography.displayHero.fontFamily, AppFont.serif);
      expect(AppTypography.body.fontFamily, AppFont.sans);
      expect(AppTypography.capsLabel.letterSpacing, greaterThan(0));
    });

    test('the two hero tones are textPrimary then primary', () {
      expect(AppTypography.displayHero.color, AppColors.textPrimary);
      expect(AppTypography.displayHeroAccent.color, AppColors.primary);
    });
  });

  group('§7.3 spacing and §7.4 radii', () {
    test('the scale is a 4-pt grid', () {
      for (final double v in <double>[
        AppSpacing.xxs, AppSpacing.xs, AppSpacing.sm, AppSpacing.md,
        AppSpacing.lg, AppSpacing.xl, AppSpacing.xxl, AppSpacing.xxxl,
      ]) {
        expect(v % 4, 0);
      }
    });

    test('radii are ordered and the pill is fully round', () {
      expect(AppRadii.sm, lessThan(AppRadii.md));
      expect(AppRadii.md, lessThan(AppRadii.lg));
      expect(AppRadii.lg, lessThan(AppRadii.xl));
      expect(AppRadii.pill, greaterThan(AppRadii.xl));
    });
  });

  group('§7.6 icon table', () {
    test('every name referenced by the domain enums resolves', () {
      final Set<String> referenced = <String>{
        for (final RecordType t in RecordType.values) t.icon,
        for (final FactType t in FactType.values) t.icon,
        for (final TimelineEventType t in TimelineEventType.values) t.icon,
        for (final Specialty s in Specialty.values) s.icon,
      };
      final List<String> missing =
          referenced.where((String n) => !AppIcons.has(n)).toList(growable: false);
      expect(missing, isEmpty, reason: 'unmapped icon names: $missing');
      expect(AppIcons.length, greaterThan(120));
    });

    test('an unknown name degrades to a neutral circle instead of throwing', () {
      expect(AppIcons.has('definitely_not_an_icon'), isFalse);
      expect(AppIcons.byName('definitely_not_an_icon'), isNotNull);
    });
  });

  group('§6.6 confidence bands', () {
    test('thresholds match the backend', () {
      expect(ConfidenceBand.fromValue(0.85), ConfidenceBand.high);
      expect(ConfidenceBand.fromValue(1), ConfidenceBand.high);
      expect(ConfidenceBand.fromValue(0.84), ConfidenceBand.medium);
      expect(ConfidenceBand.fromValue(0.60), ConfidenceBand.medium);
      expect(ConfidenceBand.fromValue(0.59), ConfidenceBand.needsVerification);
      expect(ConfidenceBand.fromValue(null), ConfidenceBand.needsVerification);
    });

    test('an API band wins over the computed one', () {
      expect(ConfidenceBand.fromWire('high', confidence: 0.1), ConfidenceBand.high);
      expect(ConfidenceBand.fromWire('nonsense', confidence: 0.9), ConfidenceBand.high);
    });

    test('each band fills the right number of micro-bar segments', () {
      expect(ConfidenceBand.high.filledSegments, 3);
      expect(ConfidenceBand.medium.filledSegments, 2);
      expect(ConfidenceBand.needsVerification.filledSegments, 1);
    });
  });

  group('mixed date formats from the backend', () {
    test('parses every shape the backend emits', () {
      expect(AppDate.tryParse('2026-09-28T16:30:00')!.year, 2026);
      expect(AppDate.tryParse('2026-10-04T17:12:29.116164+00:00')!.year, 2026);
      expect(AppDate.tryParse('Jan 2026')!.month, 1);
      expect(AppDate.tryParse('20 Jan 2025')!.day, 20);
      expect(AppDate.tryParse('1984-03-22')!.year, 1984);
      expect(AppDate.tryParse('1984')!.year, 1984);
      expect(AppDate.tryParse('03/2022')!.month, 3);
    });

    test('returns null for unusable input instead of throwing', () {
      expect(AppDate.tryParse(null), isNull);
      expect(AppDate.tryParse(''), isNull);
      expect(AppDate.tryParse('undated'), isNull);
      expect(AppDate.tryParse('not a date'), isNull);
      expect(AppDate.date(null), 'Not dated');
      expect(AppDate.undatedLabel, 'Undated');
    });

    test('range repeats the month only when the range crosses one', () {
      expect(AppDate.range('2026-05-12', '2026-05-18'), '12 – 18 May 2026');
      expect(AppDate.range('2026-05-12', '2026-05-12'), '12 May 2026');
      expect(AppDate.range('2026-02-12', '2026-04-03'), '12 Feb – 3 Apr 2026');
      expect(AppDate.range('2025-12-30', '2026-01-02'), '30 Dec 2025 – 2 Jan 2026');
      expect(AppDate.range(null, null), 'No date range');
    });

    test('the rail label is an uppercase month over a day number', () {
      expect(AppDate.capsMonth('2026-09-28T16:30:00'), 'SEP');
      expect(AppDate.dayNumber('2026-09-28T16:30:00'), '28');
    });
  });

  group('§11.4 error to human text', () {
    test('every backend code maps to human copy', () {
      const Map<String, String> expected = <String, String>{
        'DOCUMENT_PROCESSING_FAILED': 'We couldn\'t read this document. Try a clearer scan.',
        'OCR_FAILED': 'We couldn\'t read this document. Try a clearer scan.',
        'LLM_UNAVAILABLE': 'AI is temporarily unavailable. Showing the last available information.',
        'STT_FAILED': 'We couldn\'t transcribe that recording.',
        'GATE1_BLOCKED': 'Approval is on hold: some items need your review.',
      };
      expected.forEach((String code, String text) {
        expect(ErrorMessages.forCode(code), text);
      });
    });

    test('network and timeout have their own wording', () {
      expect(ErrorMessages.forCode('NETWORK'), ErrorMessages.network);
      expect(ErrorMessages.forCode('TIMEOUT'), ErrorMessages.timeout);
    });

    test('unknown codes never leak a raw message', () {
      expect(ErrorMessages.forCode('SOMETHING_ELSE'), 'Something went wrong.');
      expect(ErrorMessages.forCode(null), 'Something went wrong.');
    });
  });

  group('§0.2 rule 7 — no hardcoded base URL', () {
    test('the base URL is built by the config layer only', () {
      expect(AppConfig.apiPrefix, '/api/v1');
      expect(AppConfig.baseUrl, endsWith('/api/v1'));
      expect(AppConfig.baseUrl, isNot(contains('undefined')));
    });

    test('normalisation strips the prefix, trailing slashes and adds a scheme', () {
      expect(AppConfig.normalise('http://x:8000/'), 'http://x:8000');
      expect(AppConfig.normalise('http://x:8000/api/v1'), 'http://x:8000');
      expect(AppConfig.withScheme('192.168.1.10:8000'), 'http://192.168.1.10:8000');
      expect(AppConfig.withScheme(''), '');
    });

    test('the platform default never points at a loopback the device cannot use', () {
      // Android emulators need 10.0.2.2; that is the compiled-in default.
      expect(AppConfig.androidEmulatorHost, '10.0.2.2');
      expect(AppConfig.baseUrlHints, isNotEmpty);
    });

    test('app source contains no inline host literals outside the config layer', () {
      final List<File> files = Directory('lib')
          .listSync(recursive: true)
          .whereType<File>()
          .where((File f) => f.path.endsWith('.dart'))
          .toList();
      final RegExp host = RegExp(r'https?://(127\.0\.0\.1|localhost|10\.0\.2\.2)');
      final List<String> offenders = <String>[];
      for (final File f in files) {
        if (f.path.endsWith('app_config.dart')) continue;
        if (host.hasMatch(f.readAsStringSync())) {
          offenders.add(f.path);
        }
      }
      expect(offenders, isEmpty, reason: 'hardcoded host in $offenders');
    });
  });

  group('ThemeData', () {
    test('assembles with the plan tokens', () {
      final ThemeData theme = AppTheme.light();
      expect(theme.colorScheme.primary, AppColors.primary);
      expect(theme.scaffoldBackgroundColor, AppColors.bgCanvas);
      expect(theme.textTheme.bodyLarge?.fontFamily, AppFont.sans);
      expect(theme.pageTransitionsTheme.builders, isNotEmpty);
    });
  });
}
