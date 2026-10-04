import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/constants/app_assets.dart';
import '../../core/models/document.dart';
import '../../core/models/patient.dart';
import '../../core/repositories/providers.dart';
import '../../core/theme/app_colors.dart';
import '../../shared/widgets/app_icons.dart';
import '../../shared/widgets/primitives.dart';
import '../../shared/widgets/sheets.dart';
import '../memory/memory_screen.dart';
import 'documents_screen.dart';

/// `Records` shell tab — plan §8. Operates on the active patient.
class RecordsTabScreen extends ConsumerWidget {
  const RecordsTabScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final String? patientId = ref.watch(activePatientIdProvider);

    if (patientId == null) {
      return const Scaffold(
        backgroundColor: AppColors.bgCanvas,
        body: SafeArea(
          child: Column(
            children: <Widget>[
              TopBar(
                  title: 'Records',
                  subtitle: 'Evidence library',
                  showLeading: false),
              Expanded(
                child: NoActivePatient(
                  title: 'No patient selected',
                  message:
                      'Records are shown for one patient at a time. Choose a patient to see '
                      'their uploaded evidence.',
                ),
              ),
            ],
          ),
        ),
      );
    }

    return DocumentsScreen(patientId: patientId, embedded: true);
  }
}

/// `Memory` shell tab — plan §8 / §9.18.
class MemoryTabScreen extends ConsumerWidget {
  const MemoryTabScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final String? patientId = ref.watch(activePatientIdProvider);

    if (patientId == null) {
      return const Scaffold(
        backgroundColor: AppColors.bgCanvas,
        body: SafeArea(
          child: Column(
            children: <Widget>[
              TopBar(
                  title: 'Clinical Memory',
                  subtitle: 'Verified facts',
                  showLeading: false),
              Expanded(
                child: NoActivePatient(
                  title: 'No patient selected',
                  message:
                      'Verified clinical memory belongs to a patient. Choose one to review '
                      'what has been approved.',
                ),
              ),
            ],
          ),
        ),
      );
    }

    return ClinicalMemoryScreen(patientId: patientId, embedded: true);
  }
}

/// Sub-line used by both tabs: `Demo Patient • 52 yrs`.
String tabSubtitle(String? patientId, List<Patient> patients) {
  if (patientId == null) return 'No patient selected';
  for (final Patient p in patients) {
    if (p.id == patientId) return '${p.fullName} • ${p.ageLabel}';
  }
  return 'Patient selected';
}

/// Ambient still for a record's thumbnail tile.
String recordAmbient(int index) =>
    kPatientAmbientImages[index % kPatientAmbientImages.length];

/// Icon used for the record-type glyph on the tile.
String recordGlyph(ClinicalDocument doc) => doc.documentType.icon;

/// Keeps `AppIcons` referenced for the tab headers.
IconData tabIcon(String name) => AppIcons.byName(name);
