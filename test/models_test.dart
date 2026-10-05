import 'dart:convert';
import 'dart:io';

import 'package:clinicsync/core/constants/enums.dart';
import 'package:clinicsync/core/models/clinical_fact.dart';
import 'package:clinicsync/core/models/clinical_memory.dart';
import 'package:clinicsync/core/models/consultation.dart';
import 'package:clinicsync/core/models/doctor_brief.dart';
import 'package:clinicsync/core/models/document.dart';
import 'package:clinicsync/core/models/investigation.dart';
import 'package:clinicsync/core/models/json_utils.dart';
import 'package:clinicsync/core/models/medication.dart';
import 'package:clinicsync/core/models/patient.dart';
import 'package:clinicsync/core/models/specialty.dart';
import 'package:clinicsync/core/models/timeline_event.dart';
import 'package:clinicsync/core/utils/confidence_band.dart';
import 'package:flutter_test/flutter_test.dart';

/// Fixtures are captured from the live backend by `tools/capture_fixtures.py`,
/// so these tests fail if the contract ever drifts.
Map<String, dynamic> load(String name) {
  final File file = File('test/fixtures/$name.json');
  expect(file.existsSync(), isTrue, reason: 'missing fixture $name.json — run tools/capture_fixtures.py');
  return Map<String, dynamic>.from(jsonDecode(file.readAsStringSync()) as Map);
}

List<Map<String, dynamic>> dataList(String name) => asMapList(load(name)['data']);

Map<String, dynamic> dataMap(String name) => asMap(load(name)['data']);

void main() {
  group('json_utils tolerance', () {
    test('coerces loosely and never throws on odd input', () {
      expect(asInt('42'), 42);
      expect(asInt(7.9), 7);
      expect(asInt(null), isNull);
      expect(asDouble('0.95'), 0.95);
      expect(asDouble('8,400'), 8400.0); // comma is a thousands separator
      expect(asDouble(' 7.8 '), 7.8); // whitespace tolerated
      expect(asBool('true'), isTrue);
      expect(asBool('no'), isFalse);
      expect(asBool(null, fallback: true), isTrue);
      expect(asString(''), isNull);
      expect(asStringOr(null, 'fallback'), 'fallback');
      expect(asList('nope'), isEmpty);
      expect(asMap('nope'), isEmpty);
    });

    test('unknown fields are ignored', () {
      final Patient p = Patient.fromJson(<String, dynamic>{
        'id': 'pat_1',
        'full_name': 'Ada',
        'totally_new_field': 123,
      });
      expect(p.id, 'pat_1');
      expect(p.fullName, 'Ada');
    });
  });

  group('Patient', () {
    test('parses the real response and derives a monogram', () {
      final Patient p = Patient.fromJson(dataMap('patient'));
      expect(p.id, 'pat_demo_patient_001');
      expect(p.fullName, 'Demo Patient');
      expect(p.ageYears, 52);
      expect(p.age, 52);
      expect(p.monogram, 'DP');
      expect(p.sexLabel, 'Male');
      expect(p.isDemo, isTrue);
      expect(p.ageLabel, '52 yrs');
    });

    test('falls back to date_of_birth when age_years is null', () {
      final Patient p = Patient.fromJson(<String, dynamic>{
        'id': 'pat_2',
        'full_name': 'Grace Hopper',
        'date_of_birth': '1906-12-09',
        'age_years': null,
      });
      expect(p.age, isNotNull);
      expect(p.age! > 100, isTrue);
      expect(p.monogram, 'GH');
    });

    test('missing optional fields stay null', () {
      final Patient p = Patient.fromJson(<String, dynamic>{'id': 'p', 'full_name': 'X'});
      expect(p.ageYears, isNull);
      expect(p.age, isNull);
      expect(p.ageLabel, 'Age not recorded');
      expect(p.sexLabel, 'Sex not recorded');
      expect(p.lastSeenLabel, 'No activity yet');
    });
  });

  group('PatientOverview', () {
    test('parses the aggregate and its stat counts', () {
      final PatientOverview o = PatientOverview.fromJson(dataMap('patient_overview'));
      expect(o.patient.id, 'pat_demo_patient_001');
      expect(o.sourceCount, greaterThan(0));
      expect(o.latestBrief, isNotNull);
      expect(o.timelinePreview, isNotEmpty);
      expect(o.currentMedications, isNotEmpty);
      expect(o.latestInvestigations, isNotEmpty);
      expect(o.memorySummary, isNotEmpty);
      expect(o.openIssueTotal, greaterThan(0));
      expect(o.hasClinicalFacts, isTrue);
    });

    test('overview keys are read from the backend names, not the old names', () {
      final PatientOverview o = PatientOverview.fromJson(<String, dynamic>{
        'patient': <String, dynamic>{'id': 'p', 'full_name': 'A'},
        'source_count': 3,
        'open_issue_counts': <String, dynamic>{'medication_conflict': 1},
      });
      expect(o.sourceCount, 3);
      expect(o.conflictCount, 1);
    });
  });

  group('ClinicalDocument', () {
    test('parses the real document list', () {
      final List<ClinicalDocument> docs = dataList('documents').map(ClinicalDocument.fromJson).toList();
      expect(docs, isNotEmpty);
      final ClinicalDocument d = docs.first;
      expect(d.id, startsWith('doc_'));
      expect(d.documentType, RecordType.dischargeSummary);
      expect(d.processingStatus, ProcessingStatus.complete);
      expect(d.isFallback, isFalse);
      expect(d.sizeLabel, isNotEmpty);
      expect(d.displayName, isNotEmpty);
      expect(d.canProcess, isFalse);
    });

    test('unknown document type degrades to `unknown`', () {
      final ClinicalDocument d = ClinicalDocument.fromJson(<String, dynamic>{
        'id': 'doc_x',
        'original_filename': 'a.pdf',
        'document_type': 'quantum_report',
      });
      expect(d.documentType, RecordType.unknown);
    });
  });

  group('ProcessingStatusSnapshot', () {
    test('parses the 6-stage pipeline and derives progress', () {
      final ProcessingStatusSnapshot s =
          ProcessingStatusSnapshot.fromJson(dataMap('document_status'));
      expect(s.documentId, startsWith('doc_'));
      expect(s.stages, hasLength(6));
      expect(s.progress, inInclusiveRange(0.0, 1.0));
      expect(s.isTerminal, isTrue);
      expect(s.stages.first.stage, PipelineStage.uploaded);
    });
  });

  group('TimelineEvent', () {
    test('parses real events and flags undated ones', () {
      final List<TimelineEvent> events = dataList('timeline').map(TimelineEvent.fromJson).toList();
      expect(events, isNotEmpty);
      expect(events.any((TimelineEvent e) => e.relatedFactIds.isNotEmpty), isTrue);
      expect(events.any((TimelineEvent e) => e.sourceDocumentId != null), isTrue);
      // The seeded `approved_note` event is the newest and carries no facts.
      final TimelineEvent approved =
          events.firstWhere((TimelineEvent e) => e.eventType == TimelineEventType.approvedNote);
      expect(approved.relatedFactIds, isEmpty);
      final TimelineEvent undated = TimelineEvent.fromJson(<String, dynamic>{
        'id': 'evt_1',
        'title': 'Something',
        'event_date': null,
      });
      expect(undated.isUndated, isTrue);
    });
  });

  group('Medication', () {
    test('parses the real list and surfaces conflicts', () {
      final List<Medication> meds = dataList('medications').map(Medication.fromJson).toList();
      expect(meds, isNotEmpty);
      final Medication metformin = meds.firstWhere((Medication m) => m.canonicalName == 'metformin');
      expect(metformin.displayName, 'Metformin');
      expect(metformin.hasConflict, isTrue);
      expect(metformin.conflictIds, isNotEmpty);
      expect(metformin.confidenceBand.label, isNotEmpty);
      expect(metformin.doseLine, isNotEmpty);
      expect(metformin.frequencyCodeLabel, isNotEmpty);
      // The list payload has no group_key, so the history path is the canonical name.
      expect(metformin.historyPathSegment, 'metformin');
    });

    test('has_conflict defaults to true when conflict_ids is non-empty', () {
      final Medication m = Medication.fromJson(<String, dynamic>{
        'id': 'med_1',
        'canonical_name': 'x',
        'conflict_ids': <String>['iss_1'],
      });
      expect(m.hasConflict, isTrue);
    });

    test('history strength line is human readable', () {
      final MedicationHistoryEntry e = MedicationHistoryEntry.fromJson(
        dataList('medication_history').first,
      );
      expect(e.strengthLine, isNotEmpty);
      expect(e.frequencyCodeLabel, isNotEmpty);
    });
  });

  group('Investigation', () {
    test('uses `test_name` (not `test_name_canonical`) for the list', () {
      final List<Investigation> inv =
          dataList('investigations').map(Investigation.fromJson).toList();
      expect(inv, isNotEmpty);
      final Investigation hba1c = inv.firstWhere((Investigation i) => i.testName == 'hba1c');
      expect(hba1c.displayName, 'HbA1c');
      expect(hba1c.displayValue, '7.8');
      expect(hba1c.displayUnit, '%');
      expect(hba1c.abnormalFlag, AbnormalFlag.high);
      expect(hba1c.referenceLine, isNotEmpty);
      expect(hba1c.groupKey, contains('hba1c'));
    });

    test('trend parses series, direction and the non-causal description', () {
      final InvestigationTrend t = InvestigationTrend.fromJson(dataMap('investigation_trend'));
      expect(t.test, 'hba1c');
      expect(t.series, hasLength(3));
      expect(t.hasEnoughPoints, isTrue);
      expect(t.direction, TrendDirection.down);
      expect(t.delta, -0.6);
      expect(t.latestValue, 7.8);
      expect(t.descriptionText, contains('decreasing'));
      // The client's own fallback must never assert a cause.
      expect(t.descriptionText.toLowerCase(), isNot(contains('because')));
    });

    test('the empty-series trend variant omits unit/latest_value', () {
      final InvestigationTrend t = InvestigationTrend.fromJson(<String, dynamic>{
        'test': 'tsh',
        'series': <dynamic>[],
        'direction': 'stable',
        'delta': 0.0,
        'description': 'No recorded measurements for tsh.',
      });
      expect(t.unit, isNull);
      expect(t.latestValue, isNull);
      expect(t.latestFlag, isNull);
      expect(t.hasEnoughPoints, isFalse);
    });

    test('series values may arrive as strings when value_numeric is null', () {
      final TrendPoint p = TrendPoint.fromJson(<String, dynamic>{
        'id': 'inv_1',
        'value': '7.8',
        'date': 'Sep 2026',
      });
      expect(p.hasNumericValue, isTrue);
      expect(p.value, 7.8);
    });
  });

  group('ClinicalIssue', () {
    test('parses conflicts and missing information', () {
      final List<ClinicalIssue> issues = dataList('issues').map(ClinicalIssue.fromJson).toList();
      expect(issues, isNotEmpty);
      final ClinicalIssue conflict =
          issues.firstWhere((ClinicalIssue i) => i.issueType == IssueType.medicationConflict);
      expect(conflict.isConflict, isTrue);
      expect(conflict.severity, Severity.high);
      expect(conflict.sourceLines, isNotEmpty);

      final ClinicalIssue missing =
          issues.firstWhere((ClinicalIssue i) => i.issueType == IssueType.missingInformation);
      expect(missing.isMissingInfo, isTrue);
      expect(missing.prompt, startsWith('Potentially missing'));
    });

    test('reads both conflict sources from detail_json, not the prose', () {
      final ClinicalIssue conflict = ClinicalIssue.fromJson(
        <String, dynamic>{
          'id': 'iss_x',
          'issue_type': 'medication_conflict',
          'title': 'Conflicting dosage instructions for Metformin',
          'description':
              'Two records contain different Metformin instructions: A vs B.',
          'detail_json': <String, dynamic>{
            'drug': 'metformin',
            'source_1': <String, dynamic>{
              'doc': 'rx1.pdf',
              'dose': '500.0mg',
              'freq': 'BD',
            },
            'source_2': <String, dynamic>{
              'doc': 'rx2.pdf',
              'dose': '1000.0mg',
              'freq': 'BD',
            },
          },
        },
      );
      expect(conflict.drug, 'metformin');
      expect(conflict.sourceLines, <String>[
        '500.0mg · BD · rx1.pdf',
        '1000.0mg · BD · rx2.pdf',
      ]);
    });

    test('falls back to the description when detail_json has no sources', () {
      final ClinicalIssue conflict = ClinicalIssue.fromJson(
        <String, dynamic>{
          'id': 'iss_y',
          'issue_type': 'medication_conflict',
          'description': 'Two records differ: Tab. Metformin 500 mg BD vs '
              'Tab. Metformin 1000 mg BD.',
        },
      );
      expect(conflict.sourceLines, <String>[
        'Tab. Metformin 500 mg BD',
        'Tab. Metformin 1000 mg BD',
      ]);
    });

    test('a conflict with neither source yields no side-by-side block', () {
      final ClinicalIssue conflict =
          ClinicalIssue.fromJson(<String, dynamic>{'id': 'iss_z'});
      expect(conflict.sourceLines, isEmpty);
      expect(conflict.description, isNull);
    });

    test('the capture fixtures agree with the live detail_json shape', () {
      // Guards the parse path: a captured medication conflict must yield
      // exactly two structured source lines, not a prose split.
      final ClinicalIssue conflict = dataList('issues')
          .map(ClinicalIssue.fromJson)
          .firstWhere((ClinicalIssue i) => i.isConflict);
      expect(conflict.sourceLines, hasLength(2));
      for (final String line in conflict.sourceLines) {
        expect(line, isNotEmpty);
        expect(line, isNot(contains(' vs ')),
            reason: 'must be a structured source, not the raw description');
      }
    });
  });

  group('ClinicalFact and evidence', () {
    test('parses facts with band, provenance and verification', () {
      final List<ClinicalFact> facts = dataList('facts').map(ClinicalFact.fromJson).toList();
      expect(facts, isNotEmpty);
      final ClinicalFact f = facts.first;
      expect(f.id, startsWith('fact_'));
      expect(f.confidenceBand, isNotNull);
      expect(f.confidencePercent, endsWith('%'));
      expect(f.provenanceVerified, isTrue);
      expect(f.verificationStatus, isNotNull);
      expect(f.pageChipLabel, startsWith('Page'));
    });

    test('parses the evidence payload including the verbatim span', () {
      final FactEvidence e = FactEvidence.fromJson(dataMap('fact_evidence'));
      expect(e.factId, startsWith('fact_'));
      expect(e.source.documentFilename, endsWith('.pdf'));
      expect(e.source.hasVerbatim, isTrue);
      expect(e.source.pageNumber, 1);
      expect(e.provenanceVerified, isTrue);
    });
  });

  group('DoctorBrief', () {
    test('parses every section of the real brief', () {
      final DoctorBrief b = DoctorBrief.fromJson(dataMap('brief_latest'));
      expect(b.patientId, 'pat_demo_patient_001');
      expect(b.chiefComplaint?.hasText, isTrue);
      expect(b.chiefComplaint!.evidenceIds, isNotEmpty);
      expect(b.relevantHistory, isNotEmpty);
      expect(b.currentMedications, isNotEmpty);
      expect(b.recentInvestigations, isNotEmpty);
      expect(b.importantTrends, isNotEmpty);
      expect(b.missingInformation, isNotEmpty);
      expect(b.evidenceShortcuts, isNotEmpty);
      expect(b.allergies, isNotEmpty);
      expect(b.attentionItems, isNotEmpty);
      expect(b.contradictions, isNotEmpty);
      expect(b.disclaimer, isNotNull);
      expect(b.disclaimer, contains('Not a diagnosis'));
      expect(b.isEmpty, isFalse);
    });

    test('brief trend series uses `val`, not `value`', () {
      final DoctorBrief b = DoctorBrief.fromJson(<String, dynamic>{
        'patient': <String, dynamic>{'id': 'p', 'name': 'A'},
        'important_trends': <dynamic>[
          <String, dynamic>{
            'test': 'HbA1c',
            'series': <dynamic>[
              <String, dynamic>{'val': 8.4, 'date': 'Jan 2026'},
              <String, dynamic>{'val': 7.8, 'date': 'Sep 2026'},
            ],
            'direction': 'down',
            'description': 'decreasing',
          },
        ],
      });
      final BriefTrend t = b.importantTrends.single;
      expect(t.series, hasLength(2));
      expect(t.series.first.value, 8.4);
      expect(t.series.first.hasValue, isTrue);
    });

    test('a brief without a disclaimer still yields the mandated one', () {
      final DoctorBrief b = DoctorBrief.fromJson(<String, dynamic>{
        'patient': <String, dynamic>{'id': 'p'},
      });
      expect(b.disclaimerText, contains('Not a diagnosis'));
    });

    test('a blocked preview separates infrastructure from content', () {
      ApprovalPreview previewOf(List<Map<String, dynamic>> checks) =>
          ApprovalPreview.fromJson(<String, dynamic>{
            'outcome': 'blocked',
            'can_approve': false,
            'checks': checks,
          });

      // Gate 1's fail-closed path when the judge cannot be reached.
      final ApprovalPreview outage = previewOf(<Map<String, dynamic>>[
        <String, dynamic>{
          'name': 'llm_judge_faithfulness',
          'passed': false,
          'severity': 'block',
          'detail':
              'Gate 1 validation failed closed: validation judge service is unavailable.',
        },
      ]);
      expect(outage.canApprove, isFalse);
      expect(outage.blockers, hasLength(1));
      expect(outage.blockedByInfrastructure, isTrue,
          reason: 'an outage must not read as "your note is wrong"');

      // A real content block.
      final ApprovalPreview content = previewOf(<Map<String, dynamic>>[
        <String, dynamic>{
          'name': 'provenance_check',
          'passed': false,
          'severity': 'block',
          'detail': 'Unsupported claim: evidence id not found',
        },
      ]);
      expect(content.blockers, hasLength(1));
      expect(content.blockedByInfrastructure, isFalse);
      expect(content.infrastructureBlockers, isEmpty);
    });

    test('withSource marks a template-served brief, not a model-written one', () {
      final DoctorBrief brief = DoctorBrief.fromJson(<String, dynamic>{
        'patient': <String, dynamic>{'id': 'p1', 'name': 'Demo', 'age': 52},
        'chief_complaint': <String, dynamic>{'text': 'x'},
      });
      expect(brief.servedByTemplate, isFalse);
      expect(brief.withSource('llm').servedByTemplate, isFalse);
      expect(brief.withSource('fallback').servedByTemplate, isTrue);
      // Everything else must survive the copy.
      final DoctorBrief fallback = brief.withSource('fallback');
      expect(fallback.patientName, 'Demo');
      expect(fallback.chiefComplaint?.text, 'x');
    });

    test('a read-back brief keeps the label its generation_source gives it', () {
      // The brief screen must not claim a model wrote a template summary, even
      // when this session fetched it rather than generating it.
      DoctorBrief briefWith(String? source) => DoctorBrief.fromJson(
            <String, dynamic>{
              'patient': <String, dynamic>{'id': 'p1'},
              'chief_complaint': <String, dynamic>{'text': 'x'},
              if (source != null) 'generation_source': source,
            },
          );

      expect(briefWith('llm').servedByTemplate, isFalse);
      expect(briefWith('fallback_template').servedByTemplate, isTrue);
      expect(briefWith('seed').servedByTemplate, isTrue);
      // An older server that omits the field must not crash or over-claim.
      expect(briefWith(null).servedByTemplate, isFalse);
      // ...and the envelope fallback still applies for that older server.
      expect(briefWith(null).withSource('fallback').servedByTemplate, isTrue);
      // The envelope can never talk a payload out of its own provenance.
      expect(
        briefWith('fallback_template').withSource('llm').servedByTemplate,
        isTrue,
      );
    });
  });

  group('Consultation', () {
    test('parses a draft with its version and content', () {
      final Consultation c = Consultation.fromJson(dataMap('consultation'));
      expect(c.id, startsWith('cns_'));
      expect(c.currentVersion, isNotNull);
      expect(c.versionChipLabel, startsWith('v'));
      final ConsultationContent content = c.currentVersion!.content!;
      // The AI draft must leave the doctor's sections empty.
      expect(content.assessment, isEmpty);
      expect(content.plan, isEmpty);
      expect(content.followUp, isEmpty);
      expect(content.chiefComplaint, isNotEmpty);
    });

    test('content round-trips through toJson', () {
      final ConsultationContent c = ConsultationContent(
        chiefComplaint: 'Headache',
        assessment: 'Migraine',
        plan: 'Review in 4 weeks',
      );
      final ConsultationContent back = ConsultationContent.fromJson(c.toJson());
      expect(back.chiefComplaint, 'Headache');
      expect(back.assessment, 'Migraine');
      expect(back.plan, 'Review in 4 weeks');
      expect(back.copy().assessment, 'Migraine');
    });

    test('approval preview maps machine check names to doctor-facing labels', () {
      final ApprovalPreview p = ApprovalPreview.fromJson(dataMap('approve_preview'));
      expect(p.canApprove, isFalse);
      expect(p.outcome, ValidationOutcome.blocked);
      expect(p.blockers, isNotEmpty);
      expect(p.requiredAcknowledgements, greaterThan(0));
      final ApprovalCheck check = p.checks.firstWhere(
        (ApprovalCheck c) => c.name == 'authorship_state_check',
      );
      expect(check.label, 'Untouched AI draft');
      expect(check.severity, CheckSeverity.block);
    });

    test('versions parse in order', () {
      final List<ConsultationVersion> versions =
          dataList('consultation_versions').map(ConsultationVersion.fromJson).toList();
      expect(versions, isNotEmpty);
      expect(versions.first.versionNumber, greaterThanOrEqualTo(1));
      expect(versions.first.label, startsWith('v'));
    });
  });

  group('ClinicalMemory', () {
    test('parses verified memory of several types', () {
      final List<ClinicalMemoryItem> memory =
          dataList('memory').map(ClinicalMemoryItem.fromJson).toList();
      expect(memory, isNotEmpty);
      for (final ClinicalMemoryItem m in memory) {
        expect(m.verified, isTrue);
        expect(m.content.headline, isNotEmpty);
        expect(m.memoryType, isNotNull);
      }
      expect(
        memory.map((ClinicalMemoryItem m) => m.memoryType).toSet(),
        contains(MemoryType.medication),
      );
    });

    test('nested content shapes flatten into bullets', () {
      final MemoryContent c = MemoryContent.fromJson(<String, dynamic>{
        'diagnosis': 'Type 2 Diabetes Mellitus',
        'status': 'active',
      });
      expect(c.headline, 'Type 2 Diabetes Mellitus');
      expect(c.bullets.length, greaterThanOrEqualTo(2));
    });
  });

  group('VoiceNote', () {
    test('proposed facts are flagged needs-verification', () {
      final VoiceNote n = VoiceNote.fromJson(<String, dynamic>{
        'id': 'vce_1',
        'transcript_normalized': 'Patient reports polyuria.',
        'stt_model': 'whisper-large-v3',
        'stt_confidence': 0.82,
        'review_status': 'pending_review',
        'proposed_facts': <dynamic>[
          <String, dynamic>{
            'id': 'fact_x',
            'fact_type': 'symptom',
            'value': 'polyuria',
            'confidence_band': 'needs_verification',
            'verification_status': 'needs_verification',
          },
        ],
      });
      expect(n.usedFallback, isFalse);
      expect(n.proposedFacts.single.verificationStatus,
          VerificationStatus.needsVerification);
      expect(n.proposedFacts.single.confidenceBand, ConfidenceBand.needsVerification);
    });

    test('STT fallback is detectable', () {
      final VoiceNote n = VoiceNote.fromJson(<String, dynamic>{
        'id': 'vce_2',
        'transcript_raw': '[Audio recorded - transcription pending doctor review]',
        'stt_model': 'fallback',
        'stt_confidence': 0.5,
      });
      expect(n.usedFallback, isTrue);
    });
  });

  group('enum parsing is tolerant', () {
    test('every domain enum degrades safely on unknown input', () {
      expect(RecordType.fromWire('???'), RecordType.unknown);
      expect(ProcessingStatus.fromWire('???'), ProcessingStatus.uploaded);
      expect(PipelineStage.fromWire('???'), PipelineStage.uploaded);
      expect(FactType.fromWire('???'), FactType.other);
      expect(IssueType.fromWire('???'), IssueType.lowConfidenceFact);
      expect(Severity.fromWire('???'), Severity.low);
      expect(IssueStatus.fromWire('???'), IssueStatus.open);
      expect(MedicationStatus.fromWire('???'), MedicationStatus.current);
      expect(AbnormalFlag.fromWire('???'), AbnormalFlag.unknown);
      expect(TimelineEventType.fromWire('???'), TimelineEventType.other);
      expect(ConsultationOrigin.fromWire('???'), ConsultationOrigin.aiGenerated);
      expect(ConsultationStatus.fromWire('???'), ConsultationStatus.draft);
      expect(MemoryType.fromWire('???'), MemoryType.other);
      expect(CheckSeverity.fromWire('???'), CheckSeverity.info);
      expect(ValidationOutcome.fromWire('???'), ValidationOutcome.pass);
      expect(TrendDirection.fromWire('???'), TrendDirection.stable);
      expect(Specialty.fromWire('???'), Specialty.generalMedicine);
      expect(ConsultationSection.fromKey('???'), isNull);
    });

    test('ConsultationSection marks which sections the AI pre-fills', () {
      expect(ConsultationSection.chiefComplaint.aiPrefilled, isTrue);
      expect(ConsultationSection.historyOfPresentIllness.aiPrefilled, isTrue);
      expect(ConsultationSection.pastHistory.aiPrefilled, isTrue);
      expect(ConsultationSection.assessment.aiPrefilled, isFalse);
      expect(ConsultationSection.plan.aiPrefilled, isFalse);
      expect(ConsultationSection.followUp.aiPrefilled, isFalse);
      expect(ConsultationSection.examination.aiPrefilled, isFalse);
    });
  });

  group('SpecialtyOption — GET /specialties', () {
    test('binds a backend row to its glyph and label', () {
      final SpecialtyOption option = SpecialtyOption.fromJson(
        <String, dynamic>{
          'id': 'diabetology',
          'name': 'Diabetology & Endocrinology',
          'description': 'Glycemic control, metabolic profiles, renal protection',
        },
      );
      expect(option.id, 'diabetology');
      expect(option.name, 'Diabetology & Endocrinology');
      expect(option.specialty, Specialty.diabetology);
      expect(option.icon, isNotEmpty);
    });

    test('an unknown backend specialty still renders', () {
      final SpecialtyOption option = SpecialtyOption.fromJson(
        <String, dynamic>{'id': 'sleep_medicine', 'name': 'Sleep Medicine'},
      );
      expect(option.specialty, isNull,
          reason: 'no glyph yet — must not collapse into General Medicine');
      expect(option.name, 'Sleep Medicine');
      expect(option.icon, 'layers', reason: 'neutral fallback glyph');
    });

    test('a row without a name falls back to the bundled label', () {
      final SpecialtyOption option =
          SpecialtyOption.fromJson(<String, dynamic>{'id': 'cardiology'});
      expect(option.name, Specialty.cardiology.label);
    });

    test('the offline mirror matches the backend seed rows', () {
      final List<SpecialtyOption> mirror = SpecialtyOption.mirroringBackend();
      expect(mirror.map((SpecialtyOption o) => o.id),
          <String>['general_medicine', 'diabetology', 'cardiology',
              'orthopedics', 'neurology', 'pediatrics', 'other']);
      for (final SpecialtyOption o in mirror) {
        expect(o.specialty, isNotNull);
      }
    });
  });
}
