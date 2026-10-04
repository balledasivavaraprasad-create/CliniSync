import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../dev/component_gallery.dart';
import '../../dev/token_gallery.dart';
import '../../features/approval/approval_screen.dart';
import '../../features/brief/brief_screen.dart';
import '../../features/camera/camera_screen.dart';
import '../../features/consultation/consultation_screen.dart';
import '../../features/documents/documents_screen.dart';
import '../../features/documents/records_tab_screen.dart';
import '../../features/evidence/evidence_screen.dart';
import '../../features/home/home_screen.dart';
import '../../features/issues/issues_screen.dart';
import '../../features/memory/memory_screen.dart';
import '../../features/overview/patient_overview_screen.dart';
import '../../features/patients/patient_list_screen.dart';
import '../../features/processing/processing_screen.dart';
import '../../features/reconciliation/reconciliation_screen.dart';
import '../../features/timeline/timeline_screen.dart';
import '../../features/trends/lab_trend_screen.dart';
import '../../features/voice/voice_screen.dart';
import '../../shared/loading/states.dart';
import '../../shared/widgets/primitives.dart';
import '../cards/clin_cards.dart';
import 'bottom_nav.dart';
import 'route_names.dart';

/// The 4-tab shell plus every push-only route — plan §8 navigation map.
final GoRouter appRouter = GoRouter(
  initialLocation: '/home',
  debugLogDiagnostics: false,
  routes: <RouteBase>[
    ShellRoute(
      builder: (BuildContext context, GoRouterState state, Widget child) =>
          AppShell(location: state.uri.path, child: child),
      routes: <RouteBase>[
        GoRoute(
          path: '/home',
          name: RouteNames.home,
          pageBuilder: (BuildContext context, GoRouterState state) =>
              const NoTransitionPage<void>(child: HomeScreen()),
        ),
        GoRoute(
          path: '/patients',
          name: RouteNames.patients,
          pageBuilder: (BuildContext context, GoRouterState state) =>
              const NoTransitionPage<void>(child: PatientListScreen()),
        ),
        GoRoute(
          path: '/records',
          name: RouteNames.records,
          pageBuilder: (BuildContext context, GoRouterState state) =>
              const NoTransitionPage<void>(child: RecordsTabScreen()),
        ),
        GoRoute(
          path: '/memory',
          name: RouteNames.memory,
          pageBuilder: (BuildContext context, GoRouterState state) =>
              const NoTransitionPage<void>(child: MemoryTabScreen()),
        ),
      ],
    ),

    // ── Patient Overview
    GoRoute(
      path: '/patients/:id',
      name: RouteNames.patientOverview,
      builder: (BuildContext context, GoRouterState state) {
        return PatientOverviewScreen(
            patientId: state.pathParameters['id'] ?? '');
      },
    ),

    // ── Overview sub-screens
    GoRoute(
      path: '/patients/:id/timeline',
      name: RouteNames.patientTimeline,
      builder: (BuildContext context, GoRouterState state) =>
          TimelineScreen(patientId: state.pathParameters['id'] ?? ''),
    ),
    GoRoute(
      path: '/patients/:id/medications',
      name: RouteNames.patientMedications,
      builder: (BuildContext context, GoRouterState state) =>
          MedicationsScreen(patientId: state.pathParameters['id'] ?? ''),
    ),
    GoRoute(
      path: '/patients/:id/investigations',
      name: RouteNames.patientInvestigations,
      builder: (BuildContext context, GoRouterState state) =>
          InvestigationsScreen(patientId: state.pathParameters['id'] ?? ''),
    ),
    GoRoute(
      path: '/patients/:id/issues',
      name: RouteNames.patientIssues,
      builder: (BuildContext context, GoRouterState state) =>
          IssuesScreen(patientId: state.pathParameters['id'] ?? ''),
    ),
    GoRoute(
      path: '/patients/:id/facts',
      name: RouteNames.patientFacts,
      builder: (BuildContext context, GoRouterState state) =>
          FactsScreen(patientId: state.pathParameters['id'] ?? ''),
    ),
    GoRoute(
      path: '/patients/:id/documents',
      name: RouteNames.patientDocuments,
      builder: (BuildContext context, GoRouterState state) =>
          DocumentsScreen(patientId: state.pathParameters['id'] ?? ''),
    ),
    GoRoute(
      path: '/patients/:id/memory',
      name: RouteNames.patientMemory,
      builder: (BuildContext context, GoRouterState state) =>
          ClinicalMemoryScreen(patientId: state.pathParameters['id'] ?? ''),
    ),

    // ── Reconciliation
    GoRoute(
      path: '/patients/:id/medications/:groupKey/reconcile',
      name: RouteNames.medicationReconcile,
      builder: (BuildContext context, GoRouterState state) {
        return MedicationReconciliationScreen(
          patientId: state.pathParameters['id'] ?? '',
          groupKey: Uri.decodeComponent(state.pathParameters['groupKey'] ?? ''),
          medicationName: state.uri.queryParameters['name'],
        );
      },
    ),

    // ── Lab trend
    GoRoute(
      path: '/patients/:id/investigations/:groupKey/trend',
      name: RouteNames.investigationTrend,
      builder: (BuildContext context, GoRouterState state) {
        return LabTrendScreen(
          patientId: state.pathParameters['id'] ?? '',
          groupKey: Uri.decodeComponent(state.pathParameters['groupKey'] ?? ''),
          testName: state.uri.queryParameters['name'],
        );
      },
    ),

    // ── Specialty
    GoRoute(
      path: '/specialty',
      name: RouteNames.specialty,
      builder: (BuildContext context, GoRouterState state) => SpecialtyScreen(
        patientId: state.uri.queryParameters['patient'],
        title: state.uri.queryParameters['title'] ?? 'Specialty',
      ),
    ),

    // ── Brief
    GoRoute(
      path: '/patients/:id/brief',
      name: RouteNames.brief,
      builder: (BuildContext context, GoRouterState state) => BriefScreen(
        patientId: state.pathParameters['id'] ?? '',
        specialty: state.uri.queryParameters['specialty'],
      ),
    ),

    // ── Consultation
    GoRoute(
      path: '/patients/:id/consultation',
      name: RouteNames.consultation,
      builder: (BuildContext context, GoRouterState state) =>
          ConsultationScreen(
        patientId: state.pathParameters['id'] ?? '',
        consultationId: state.uri.queryParameters['cid'],
        specialty: state.uri.queryParameters['specialty'],
        briefId: state.uri.queryParameters['brief'],
      ),
    ),
    GoRoute(
      path: '/patients/:id/consultation/:cid',
      name: RouteNames.consultation,
      builder: (BuildContext context, GoRouterState state) =>
          ConsultationScreen(
        patientId: state.pathParameters['id'] ?? '',
        consultationId: Uri.decodeComponent(state.pathParameters['cid'] ?? ''),
      ),
    ),
    GoRoute(
      path: '/patients/:id/consultation/:cid/versions',
      name: RouteNames.consultationVersions,
      builder: (BuildContext context, GoRouterState state) =>
          VersionHistoryScreen(
        patientId: state.pathParameters['id'] ?? '',
        consultationId: Uri.decodeComponent(state.pathParameters['cid'] ?? ''),
      ),
    ),
    GoRoute(
      path: '/patients/:id/consultation/:cid/approve',
      name: RouteNames.approval,
      builder: (BuildContext context, GoRouterState state) => ApprovalScreen(
        patientId: state.pathParameters['id'] ?? '',
        consultationId: Uri.decodeComponent(state.pathParameters['cid'] ?? ''),
      ),
    ),

    // ── Push-only
    GoRoute(
      path: '/documents/:id/processing',
      name: RouteNames.processing,
      builder: (BuildContext context, GoRouterState state) => ProcessingScreen(
        patientId: state.uri.queryParameters['patient'] ?? '',
        documentId: Uri.decodeComponent(state.pathParameters['id'] ?? ''),
        documentName: state.uri.queryParameters['name'],
      ),
    ),
    GoRoute(
      path: '/facts/:id/evidence',
      name: RouteNames.factEvidence,
      builder: (BuildContext context, GoRouterState state) => EvidenceScreen(
          factId: Uri.decodeComponent(state.pathParameters['id'] ?? '')),
    ),
    GoRoute(
      path: '/camera/:id',
      name: RouteNames.camera,
      builder: (BuildContext context, GoRouterState state) =>
          CameraScreen(patientId: state.pathParameters['id'] ?? ''),
    ),
    GoRoute(
      path: '/voice/:id',
      name: RouteNames.voice,
      builder: (BuildContext context, GoRouterState state) =>
          VoiceScreen(patientId: state.pathParameters['id'] ?? ''),
    ),

    // ── Design-system galleries (C06 / C08 / C10 acceptance)
    GoRoute(
      path: '/galleries',
      name: RouteNames.componentGallery,
      builder: (BuildContext context, GoRouterState state) =>
          const GalleryIndexScreen(),
    ),
    GoRoute(
      path: '/galleries/tokens',
      name: RouteNames.tokenGallery,
      builder: (BuildContext context, GoRouterState state) =>
          const TokenGallery(),
    ),
    GoRoute(
      path: '/galleries/components',
      name: RouteNames.componentGallery,
      builder: (BuildContext context, GoRouterState state) =>
          const ComponentGallery(),
    ),
  ],
  errorBuilder: (BuildContext context, GoRouterState state) => Scaffold(
    backgroundColor: AppColors.bgCanvas,
    body: SafeArea(
      child: Column(
        children: <Widget>[
          TopBar(title: 'ClinSync', onLeadingTap: () => context.go('/home')),
          Expanded(
            child: EmptyState(
              icon: 'alertTriangle',
              title: 'That screen does not exist',
              message: 'The link you followed is not part of this prototype.',
              actionLabel: 'Go home',
              onAction: () => context.go('/home'),
            ),
          ),
        ],
      ),
    ),
  ),
);

/// Lists the two debug galleries.
class GalleryIndexScreen extends StatelessWidget {
  const GalleryIndexScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bgCanvas,
      body: SafeArea(
        child: Column(
          children: <Widget>[
            TopBar(title: 'Design system', onLeadingTap: () => context.pop()),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.screenH,
                  AppSpacing.md,
                  AppSpacing.screenH,
                  AppSpacing.xxl,
                ),
                children: <Widget>[
                  Text(
                    'Debug galleries used to verify fidelity against the reference image '
                    '(tasks C06, C08, C10).',
                    style: AppTypography.body,
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  LinkRowCard(
                    title: 'Token gallery',
                    label: 'Colour · type · spacing · radii · shadow',
                    thumbnailIcon: 'columns',
                    onTap: () => context.push('/galleries/tokens'),
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  LinkRowCard(
                    title: 'Component gallery',
                    label: 'Every §7.6 component in all states',
                    thumbnailIcon: 'grid',
                    onTap: () => context.push('/galleries/components'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
