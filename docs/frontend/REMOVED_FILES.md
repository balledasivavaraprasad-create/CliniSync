# Removed files — frontend-redesign (task C04)

Safety snapshot: git tag `pre-redesign-frontend`, branch `frontend-redesign`.

## Deleted Flutter source
```
lib/core/constants/api_constants.dart
lib/core/constants/app_routes.dart
lib/core/models/clinical_models.dart
lib/core/models/patient_model.dart
lib/core/networking/api_client.dart
lib/core/networking/clinical_api_service.dart
lib/core/theme/app_colors.dart
lib/core/theme/app_typography.dart
lib/core/theme/clin_theme.dart
lib/core/theme/clin_tokens.dart
lib/core/theme/clin_typography.dart
lib/core/theme/theme_controller.dart
lib/core/widgets/clin_atmosphere.dart
lib/core/widgets/clin_auth_chrome.dart
lib/core/widgets/clin_brand.dart
lib/core/widgets/clin_button.dart
lib/core/widgets/clin_field.dart
lib/core/widgets/clin_headline.dart
lib/core/widgets/clin_motion.dart
lib/core/widgets/clin_surface.dart
lib/features/auth/data/auth_models.dart
lib/features/auth/data/auth_repository.dart
lib/features/auth/screens/auth_entry_screen.dart
lib/features/auth/screens/doctor_professional_screen.dart
lib/features/auth/screens/doctor_signup_screen.dart
lib/features/auth/screens/doctor_verification_screen.dart
lib/features/auth/screens/forgot_password_screen.dart
lib/features/auth/screens/otp_verify_screen.dart
lib/features/auth/screens/patient_signup_screen.dart
lib/features/auth/screens/pending_review_screen.dart
lib/features/auth/screens/reset_password_screen.dart
lib/features/auth/screens/session_screen.dart
lib/features/auth/state/auth_controller.dart
lib/features/auth/state/auth_scope.dart
lib/features/auth/widgets/clin_credential_slot.dart
lib/features/auth/widgets/clin_otp_field.dart
lib/features/auth/widgets/clin_password_meter.dart
lib/features/auth/widgets/clin_role_selector.dart
lib/features/modern/modern_shell.dart
lib/features/modern/modern_tokens.dart
lib/features/modern/screens/modern_brief_screen.dart
lib/features/modern/screens/modern_consultation_screen.dart
lib/features/modern/screens/modern_home_screen.dart
lib/features/modern/screens/modern_hospitals_screen.dart
lib/features/modern/screens/modern_intake_screen.dart
lib/features/modern/screens/modern_medications_screen.dart
lib/features/modern/screens/modern_patient_profile_screen.dart
lib/features/modern/screens/modern_settings_screen.dart
lib/features/modern/screens/modern_timeline_screen.dart
lib/features/modern/screens/modern_trends_screen.dart
lib/features/modern/widgets/modern_card.dart
lib/features/modern/widgets/modern_pill.dart
lib/main.dart
```

## Removed test files
```
test/widget_test.dart  (tested the removed auth + modern dashboard UI)
```

## Reason per class (§3 disposition matrix)
| Path | Class | Rule applied |
|---|---|---|
| `lib/main.dart` | old entry point wiring `features/auth` + `features/modern` | REMOVE |
| `lib/core/theme/**` (`app_colors`, `app_typography`, `clin_theme`, `clin_tokens`, `clin_typography`, `theme_controller`) | old theme, dark-mode controller, not built from §7 tokens | REMOVE |
| `lib/core/widgets/**` (`clin_atmosphere`, `clin_auth_chrome`, `clin_brand`, `clin_button`, `clin_field`, `clin_headline`, `clin_motion`, `clin_surface`) | landing-page CSS ports, auth chrome, dead video layer | REMOVE |
| `lib/core/models/**` (`clinical_models.dart`, `patient_model.dart`) | field names mismatched the backend contract (`name`/`gender`/`last_activity` vs `full_name`/`sex`/`last_activity_at`) | REPLACE (rewritten per §10–§12) |
| `lib/core/networking/**` (`api_client.dart`, `clinical_api_service.dart`) | 8 of 14 endpoint paths did not exist on the backend; error parser read `message`/`detail` at the wrong level | REPLACE |
| `lib/core/constants/**` (`api_constants.dart`, `app_routes.dart`) | hardcoded `http://127.0.0.1:8000`; superseded by `core/config` + `core/constants/api_paths.dart` | REPLACE |
| `lib/features/auth/**` (18 files) | login/OTP/signup/profile — explicitly forbidden by plan §0.2 rule 4 and §0.2 rule 11 (no auth UI). Backend has no auth router (`deps.get_current_user` is a stub). | REMOVE |
| `lib/features/modern/**` (14 files) | the previous dashboard being replaced | REMOVE |

## Preserved
`android/`, `macos/`, `web/`, `pubspec.yaml` (rewritten in place), `assets/`, `backend/`, `tests/`.
