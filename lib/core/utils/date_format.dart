import 'package:intl/intl.dart';

/// Defensive date helpers — plan §10, §6.6 rule 5.
///
/// The backend emits **mixed** date shapes, so every parse is defensive:
///  * naive ISO-8601 from SQLite columns (`2026-09-28T16:30:00`)
///  * tz-aware ISO for `brief.generated_at` (`…+00:00`)
///  * `%b %Y` display strings inside trend series (`Jan 2026`)
///  * free-text `patient.date_of_birth` (`1984-03-22`, `1984`, `03/2022`)
///  * `20 Jan 2025` inside human sentences
///  * the literal `undated`
abstract final class AppDate {
  const AppDate._();

  static final DateFormat _day = DateFormat('d MMM yyyy');
  static final DateFormat _dayShort = DateFormat('d MMM');
  static final DateFormat _monthYear = DateFormat('MMM yyyy');
  static final DateFormat _capsMonth = DateFormat('MMM');
  static final DateFormat _time = DateFormat('HH:mm');
  static final DateFormat _stamp = DateFormat('d MMM · HH:mm');
  static final DateFormat _isoDate = DateFormat('yyyy-MM-dd');

  static const String undatedLabel = 'Undated';
  static const String notDatedLabel = 'Not dated';

  /// Parses any of the backend's date shapes. Returns null when unusable.
  static DateTime? tryParse(Object? raw) {
    if (raw == null) return null;
    if (raw is DateTime) return raw;
    final String s = raw.toString().trim();
    if (s.isEmpty || s.toLowerCase() == 'undated') return null;

    // `%b %Y`, e.g. "Jan 2026".
    final RegExpMatch? abbrev =
        RegExp(r'^([A-Za-z]{3})\s+(\d{4})$').firstMatch(s);
    if (abbrev != null) {
      final DateTime? parsed = DateFormat('MMM yyyy')
          .tryParse('${abbrev.group(1)} ${abbrev.group(2)}');
      if (parsed != null) return parsed;
    }
    // "20 Jan 2025"
    if (RegExp(r'^\d{1,2}\s+[A-Za-z]{3}\s+\d{4}$').hasMatch(s)) {
      final DateTime? parsed = DateFormat('d MMM yyyy').tryParse(s);
      if (parsed != null) return parsed;
    }
    // ISO-8601, with or without offset / fractional seconds.
    final DateTime? iso = DateTime.tryParse(s);
    if (iso != null) return iso.toLocal();
    // "1984" or "03/2022"
    final List<String> parts = s.split(RegExp(r'[-/.]'));
    if (parts.isNotEmpty && int.tryParse(parts.first) != null) {
      if (parts.length == 1) {
        final int y = int.parse(parts.first);
        if (y > 1800 && y < 2200) return DateTime(y);
      } else if (parts.length == 2) {
        final int? mm = int.tryParse(parts[0]);
        final int? yy = int.tryParse(parts[1]);
        if (mm != null && yy != null) {
          return DateTime(yy < 100 ? 2000 + yy : yy, mm);
        }
      }
    }
    return null;
  }

  /// `28 Sep 2026`
  static String date(Object? raw) {
    final DateTime? d = tryParse(raw);
    return d == null ? notDatedLabel : _day.format(d);
  }

  /// `28 Sep`
  static String dayMonth(Object? raw) {
    final DateTime? d = tryParse(raw);
    return d == null ? undatedLabel : _dayShort.format(d);
  }

  /// `Sep 2026`
  static String monthYear(Object? raw) {
    final DateTime? d = tryParse(raw);
    return d == null ? undatedLabel : _monthYear.format(d);
  }

  /// `SEP` — the rail label above a timeline node.
  static String capsMonth(Object? raw) {
    final DateTime? d = tryParse(raw);
    return d == null ? '—' : _capsMonth.format(d).toUpperCase();
  }

  /// Day-of-month number for a timeline node.
  static String dayNumber(Object? raw) {
    final DateTime? d = tryParse(raw);
    return d == null ? '?' : DateFormat('d').format(d);
  }

  static String time(Object? raw) {
    final DateTime? d = tryParse(raw);
    return d == null ? '—' : _time.format(d);
  }

  /// `28 Sep · 16:30`
  static String stamp(Object? raw) {
    final DateTime? d = tryParse(raw);
    return d == null ? undatedLabel : _stamp.format(d);
  }

  static String isoDate(Object? raw) {
    final DateTime? d = tryParse(raw);
    return d == null ? '' : _isoDate.format(d);
  }

  /// `12 – 18 May 2026`, `28 Sep 2026`, or `12 Feb – 3 Apr 2026`.
  ///
  /// The month is only repeated when the range crosses into a different month,
  /// so a cross-year range always shows both years.
  static String range(Object? a, Object? b) {
    final DateTime? da = tryParse(a);
    final DateTime? db = tryParse(b);
    if (da == null && db == null) return 'No date range';
    if (da == null) return 'Until ${date(db)}';
    if (db == null) return date(da);

    if (_isSameDay(da, db)) return date(da);
    final bool sameYear = da.year == db.year;
    final bool sameMonth = sameYear && da.month == db.month;

    final String start = sameMonth
        ? DateFormat('d').format(da)
        : DateFormat(sameYear ? 'd MMM' : 'd MMM yyyy').format(da);
    final String end =
        DateFormat(sameYear ? 'd MMM yyyy' : 'd MMM yyyy').format(db);
    return '$start – $end';
  }

  static bool _isSameDay(DateTime a, DateTime b) =>
      a.year == b.year && a.month == b.month && a.day == b.day;

  /// `Today`, `3d ago`, `12 Sep 2026`.
  static String relative(Object? raw) {
    final DateTime? d = tryParse(raw);
    if (d == null) return 'No activity yet';
    final Duration diff = DateTime.now().difference(d);
    if (diff.inMinutes < 1) return 'Just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    if (diff.inDays == 1) return 'Yesterday';
    if (diff.inDays < 7) return '${diff.inDays}d ago';
    return _day.format(d);
  }

  /// `Last seen 28 Sep 2026` / `No records yet`.
  static String lastSeen(Object? raw) {
    final DateTime? d = tryParse(raw);
    if (d == null) return 'Last seen —';
    return 'Last seen ${_day.format(d)}';
  }

  /// Age from `age_years`, else derived from `date_of_birth`.
  static int? age({required int? ageYears, required Object? dateOfBirth}) {
    if (ageYears != null && ageYears > 0) return ageYears;
    final DateTime? dob = tryParse(dateOfBirth);
    if (dob == null) return null;
    final DateTime now = DateTime.now();
    int years = now.year - dob.year;
    final bool hadBirthday =
        now.month > dob.month || (now.month == dob.month && now.day >= dob.day);
    if (!hadBirthday) years -= 1;
    return (years < 0 || years > 130) ? null : years;
  }

  /// `52 yrs` / `Age not recorded`.
  static String ageLabel(
      {required int? ageYears, required Object? dateOfBirth}) {
    final int? a = age(ageYears: ageYears, dateOfBirth: dateOfBirth);
    return a == null ? 'Age not recorded' : '$a yrs';
  }
}
