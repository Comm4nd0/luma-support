import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import 'package:provider/provider.dart';

import '../services/api_client.dart';
import '../services/settings_service.dart';
import '../../src/widgets/luma_icon.dart';

/// User-tweakable mobile preferences: theme, push quiet hours, biometric
/// app lock. The quiet-hours fields also push to /auth/users/me/ so the
/// server-side push fan-out respects them.
class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final settings = context.watch<SettingsService>();
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const _SectionHeader('Appearance'),
          _ThemeModeTile(current: settings.themeMode, onChanged: (m) {
            settings.setThemeMode(m);
          }),

          const SizedBox(height: 16),
          const _SectionHeader('Security'),
          SwitchListTile(
            value: settings.biometricRequired,
            onChanged: (v) => settings.setBiometricRequired(v),
            secondary: const LumaIcon(PhosphorIconsDuotone.fingerprint),
            title: const Text('Require biometric on open'),
            subtitle: const Text(
              'Prompt for Face ID / fingerprint when the app comes back '
              'to the foreground.',
            ),
          ),
          ListTile(
            leading: const LumaIcon(PhosphorIconsDuotone.keyhole),
            title: const Text('Recovery codes'),
            subtitle: const Text('One-shot codes for when you lose your authenticator'),
            trailing: const LumaIcon(PhosphorIconsDuotone.caretRight),
            onTap: () => context.push('/settings/recovery-codes'),
          ),
          ListTile(
            leading: const LumaIcon(PhosphorIconsDuotone.devices),
            title: const Text('Active sessions'),
            subtitle: const Text('See where you are signed in and sign out remotely'),
            trailing: const LumaIcon(PhosphorIconsDuotone.caretRight),
            onTap: () => context.push('/settings/sessions'),
          ),

          const SizedBox(height: 16),
          const _SectionHeader('Push notifications'),
          _QuietHoursTile(settings: settings),
          SwitchListTile(
            value: settings.quietHoursCriticalOverride,
            onChanged: settings.hasQuietHours
                ? (v) {
                    settings.setQuietHours(
                      start: settings.quietHoursStart,
                      end: settings.quietHoursEnd,
                      criticalOverride: v,
                    );
                    _pushQuietHours(context);
                  }
                : null,
            secondary: const LumaIcon(PhosphorIconsDuotone.warningCircle),
            title: const Text('Let critical tickets through'),
            subtitle: const Text(
              'Wake me for critical tickets and SLA warnings even during '
              'quiet hours. Strongly recommended.',
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _pushQuietHours(BuildContext context) async {
    // Best-effort: write the same fields to /auth/users/me/ so server
    // send_push respects the window. Fails silently — local state is
    // already saved.
    try {
      final api = context.read<ApiClient>();
      final settings = context.read<SettingsService>();
      await api.dio.patch<dynamic>(
        '/auth/users/me/',
        data: {
          'quiet_hours_start': settings.quietHoursStart,
          'quiet_hours_end': settings.quietHoursEnd,
          'quiet_hours_critical_override':
              settings.quietHoursCriticalOverride,
        },
      );
    } on DioException {
      // No-op; settings are persisted locally and will retry on next change.
    }
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader(this.label);
  final String label;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(left: 4, bottom: 4),
      child: Text(
        label.toUpperCase(),
        style: TextStyle(
          fontSize: 11,
          color: Theme.of(context).colorScheme.onSurface.withOpacity(0.6),
          letterSpacing: 1.2,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

class _ThemeModeTile extends StatelessWidget {
  const _ThemeModeTile({required this.current, required this.onChanged});
  final ThemeMode current;
  final ValueChanged<ThemeMode> onChanged;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(8),
        child: SegmentedButton<ThemeMode>(
          segments: const [
            ButtonSegment(
              value: ThemeMode.system,
              label: Text('System'),
              icon: Icon(Icons.settings_outlined),
            ),
            ButtonSegment(
              value: ThemeMode.dark,
              label: Text('Dark'),
              icon: Icon(Icons.dark_mode_outlined),
            ),
            ButtonSegment(
              value: ThemeMode.light,
              label: Text('Light'),
              icon: Icon(Icons.light_mode_outlined),
            ),
          ],
          selected: {current},
          onSelectionChanged: (set) => onChanged(set.first),
        ),
      ),
    );
  }
}

class _QuietHoursTile extends StatelessWidget {
  const _QuietHoursTile({required this.settings});
  final SettingsService settings;

  @override
  Widget build(BuildContext context) {
    final start = settings.quietHoursStart;
    final end = settings.quietHoursEnd;
    final summary = (start != null && end != null)
        ? '${_h(start)}:00 → ${_h(end)}:00 local'
        : 'Off — every push lands';
    return ListTile(
      leading: const LumaIcon(PhosphorIconsDuotone.moon),
      title: const Text('Quiet hours'),
      subtitle: Text(summary),
      trailing: const LumaIcon(PhosphorIconsDuotone.caretRight),
      onTap: () => _openPicker(context),
    );
  }

  Future<void> _openPicker(BuildContext context) async {
    final result = await showModalBottomSheet<_QuietPickResult>(
      context: context,
      builder: (_) => _QuietPickerSheet(
        start: settings.quietHoursStart,
        end: settings.quietHoursEnd,
      ),
      isScrollControlled: true,
    );
    if (result == null) return;
    await settings.setQuietHours(
      start: result.start,
      end: result.end,
      criticalOverride: settings.quietHoursCriticalOverride,
    );
    if (!context.mounted) return;
    try {
      final api = context.read<ApiClient>();
      await api.dio.patch<dynamic>(
        '/auth/users/me/',
        data: {
          'quiet_hours_start': result.start,
          'quiet_hours_end': result.end,
        },
      );
    } on DioException {
      // Local state already persisted; ignore.
    }
  }

  static String _h(int h) => h.toString().padLeft(2, '0');
}

class _QuietPickResult {
  const _QuietPickResult({required this.start, required this.end});
  final int? start;
  final int? end;
}

class _QuietPickerSheet extends StatefulWidget {
  const _QuietPickerSheet({required this.start, required this.end});
  final int? start;
  final int? end;

  @override
  State<_QuietPickerSheet> createState() => _QuietPickerSheetState();
}

class _QuietPickerSheetState extends State<_QuietPickerSheet> {
  late int? _start = widget.start;
  late int? _end = widget.end;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Quiet hours',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 8),
            const Text(
              'Suppress non-critical push between these hours, '
              'local time. Wraps midnight (e.g. 22 → 7).',
              style: TextStyle(fontSize: 12),
            ),
            const SizedBox(height: 16),
            _HourRow(
              label: 'Start',
              value: _start,
              onChanged: (v) => setState(() => _start = v),
            ),
            const SizedBox(height: 8),
            _HourRow(
              label: 'End',
              value: _end,
              onChanged: (v) => setState(() => _end = v),
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(
                  onPressed: () => Navigator.pop(
                    context,
                    const _QuietPickResult(start: null, end: null),
                  ),
                  child: const Text('Turn off'),
                ),
                const SizedBox(width: 8),
                ElevatedButton(
                  onPressed: (_start == null || _end == null)
                      ? null
                      : () => Navigator.pop(
                            context,
                            _QuietPickResult(start: _start, end: _end),
                          ),
                  child: const Text('Save'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _HourRow extends StatelessWidget {
  const _HourRow({
    required this.label,
    required this.value,
    required this.onChanged,
  });
  final String label;
  final int? value;
  final ValueChanged<int?> onChanged;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        SizedBox(width: 60, child: Text(label)),
        Expanded(
          child: DropdownButton<int?>(
            isExpanded: true,
            value: value,
            hint: const Text('(pick hour)'),
            items: [
              for (var h = 0; h < 24; h++)
                DropdownMenuItem(value: h, child: Text('${h.toString().padLeft(2, '0')}:00')),
            ],
            onChanged: onChanged,
          ),
        ),
      ],
    );
  }
}
