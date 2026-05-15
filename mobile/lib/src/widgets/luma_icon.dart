import 'package:flutter/widgets.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../theme.dart';

/// Thin wrapper around [PhosphorIcon] that tints the duotone *secondary*
/// glyph in the brand teal. Without this, the duotone fill defaults to the
/// same colour as the outline at 25% opacity — barely visible against the
/// navy background. With this, every duotone icon reads two-tone at a
/// glance.
class LumaIcon extends StatelessWidget {
  const LumaIcon(
    this.icon, {
    super.key,
    this.size,
    this.color,
    this.duotoneSecondaryColor,
  });

  final IconData icon;
  final double? size;
  final Color? color;
  final Color? duotoneSecondaryColor;

  @override
  Widget build(BuildContext context) {
    return PhosphorIcon(
      icon,
      size: size,
      color: color,
      duotoneSecondaryColor: duotoneSecondaryColor ?? kPrimary,
    );
  }
}
