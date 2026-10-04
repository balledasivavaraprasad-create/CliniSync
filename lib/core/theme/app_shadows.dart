import 'package:flutter/material.dart';

/// Soft, diffuse, slightly green-grey tinted shadows — plan §7.5. Never hard.
abstract final class AppShadows {
  const AppShadows._();

  /// Cards, list rows — y 6, blur 20, rgba(40,60,40,0.07).
  static const List<BoxShadow> card = <BoxShadow>[
    BoxShadow(
        color: Color(0x12283C28),
        offset: Offset(0, 6),
        blurRadius: 20,
        spreadRadius: -4),
  ];

  /// Search pill, bottom nav, sticky CTA bar — y 10, blur 28, 0.10.
  static const List<BoxShadow> float = <BoxShadow>[
    BoxShadow(
        color: Color(0x1A283C28),
        offset: Offset(0, 10),
        blurRadius: 28,
        spreadRadius: -6),
  ];

  /// Primary pill button — y 6, blur 16, `primary` @ 25%.
  static const List<BoxShadow> button = <BoxShadow>[
    BoxShadow(
        color: Color(0x40527A55),
        offset: Offset(0, 6),
        blurRadius: 16,
        spreadRadius: -4),
  ];

  /// Very light lift for icon tiles.
  static const List<BoxShadow> tile = <BoxShadow>[
    BoxShadow(
        color: Color(0x0F283C28),
        offset: Offset(0, 4),
        blurRadius: 12,
        spreadRadius: -3),
  ];
}
