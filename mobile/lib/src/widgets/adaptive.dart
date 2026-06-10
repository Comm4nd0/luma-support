import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';

/// iOS-style dialog / action-sheet helpers used across both platforms —
/// the app ships one Apple-feel design rather than adapting per platform.

/// Cupertino confirm dialog. Returns true when the user confirms.
Future<bool> confirmDialog(
  BuildContext context, {
  String? title,
  String? message,
  String confirmLabel = 'Confirm',
  String cancelLabel = 'Cancel',
  bool destructive = false,
}) async {
  final res = await showCupertinoDialog<bool>(
    context: context,
    builder: (ctx) => CupertinoAlertDialog(
      title: title != null ? Text(title) : null,
      content: message != null ? Text(message) : null,
      actions: [
        CupertinoDialogAction(
          onPressed: () => Navigator.pop(ctx, false),
          child: Text(cancelLabel),
        ),
        CupertinoDialogAction(
          isDestructiveAction: destructive,
          isDefaultAction: !destructive,
          onPressed: () => Navigator.pop(ctx, true),
          child: Text(confirmLabel),
        ),
      ],
    ),
  );
  return res ?? false;
}

/// Cupertino single-field text prompt. Returns null on cancel.
Future<String?> promptText(
  BuildContext context, {
  String? title,
  String? message,
  String? initial,
  String? placeholder,
  String saveLabel = 'Save',
  int maxLines = 1,
  TextInputType? keyboardType,
}) {
  final controller = TextEditingController(text: initial);
  return showCupertinoDialog<String>(
    context: context,
    builder: (ctx) => CupertinoAlertDialog(
      title: title != null ? Text(title) : null,
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (message != null) ...[
            Text(message),
            const SizedBox(height: 8),
          ],
          CupertinoTextField(
            controller: controller,
            placeholder: placeholder,
            maxLines: maxLines,
            autofocus: true,
            keyboardType: keyboardType,
          ),
        ],
      ),
      actions: [
        CupertinoDialogAction(
          onPressed: () => Navigator.pop(ctx),
          child: const Text('Cancel'),
        ),
        CupertinoDialogAction(
          isDefaultAction: true,
          onPressed: () => Navigator.pop(ctx, controller.text),
          child: Text(saveLabel),
        ),
      ],
    ),
  );
}

/// Cupertino info dialog with a single OK action.
Future<void> showAppInfo(
  BuildContext context, {
  String? title,
  required String message,
  String okLabel = 'OK',
}) {
  return showCupertinoDialog<void>(
    context: context,
    builder: (ctx) => CupertinoAlertDialog(
      title: title != null ? Text(title) : null,
      content: Text(message),
      actions: [
        CupertinoDialogAction(
          isDefaultAction: true,
          onPressed: () => Navigator.pop(ctx),
          child: Text(okLabel),
        ),
      ],
    ),
  );
}

class AppSheetAction<T> {
  const AppSheetAction({
    required this.label,
    required this.value,
    this.destructive = false,
  });

  final String label;
  final T value;
  final bool destructive;
}

/// Cupertino action sheet. Returns the chosen action's value, or null
/// when dismissed / cancelled.
Future<T?> showAppActionSheet<T>(
  BuildContext context, {
  String? title,
  String? message,
  required List<AppSheetAction<T>> actions,
  String cancelLabel = 'Cancel',
}) {
  return showCupertinoModalPopup<T>(
    context: context,
    builder: (ctx) => CupertinoActionSheet(
      title: title != null ? Text(title) : null,
      message: message != null ? Text(message) : null,
      actions: [
        for (final action in actions)
          CupertinoActionSheetAction(
            isDestructiveAction: action.destructive,
            onPressed: () => Navigator.pop(ctx, action.value),
            child: Text(action.label),
          ),
      ],
      cancelButton: CupertinoActionSheetAction(
        onPressed: () => Navigator.pop(ctx),
        child: Text(cancelLabel),
      ),
    ),
  );
}

/// iOS inset-grouped section: an uppercase caption above a rounded
/// surface with hairline dividers between rows.
class LumaGroupedSection extends StatelessWidget {
  const LumaGroupedSection({
    super.key,
    this.header,
    required this.children,
  });

  final String? header;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (header != null)
          Padding(
            padding: const EdgeInsets.only(left: 16, bottom: 6),
            child: Text(
              header!.toUpperCase(),
              style: TextStyle(
                fontSize: 13,
                letterSpacing: -0.08,
                color: theme.colorScheme.onSurface.withOpacity(0.6),
                fontWeight: FontWeight.w400,
              ),
            ),
          ),
        Material(
          color: theme.colorScheme.surface,
          clipBehavior: Clip.antiAlias,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
            side: BorderSide(color: theme.dividerTheme.color ?? theme.dividerColor, width: 0.5),
          ),
          child: Column(
            children: [
              for (var i = 0; i < children.length; i++) ...[
                if (i > 0) const Divider(height: 0.5),
                children[i],
              ],
            ],
          ),
        ),
      ],
    );
  }
}
