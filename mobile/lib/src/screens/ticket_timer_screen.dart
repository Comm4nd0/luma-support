import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../repositories/tickets_repository.dart';
import '../services/api_client.dart';

/// Per-ticket running timer.
///
/// State (`startedAt`) is persisted to shared_preferences so the timer
/// keeps running across app restarts. On stop the elapsed minutes are
/// posted via TicketsRepository.logTime — never round-tripping seconds,
/// since the backend's `minutes` field is an int.
class TicketTimerScreen extends StatefulWidget {
  const TicketTimerScreen({super.key, required this.ticketId});

  final int ticketId;

  @override
  State<TicketTimerScreen> createState() => _TicketTimerScreenState();
}

class _TicketTimerScreenState extends State<TicketTimerScreen> {
  DateTime? _startedAt;
  Timer? _tick;
  Duration _elapsed = Duration.zero;
  String _description = '';
  bool _billable = true;

  String get _prefsKey => 'timer_started_${widget.ticketId}';

  @override
  void initState() {
    super.initState();
    _restore();
  }

  Future<void> _restore() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_prefsKey);
    if (raw != null) {
      final t = DateTime.tryParse(raw);
      if (t != null) {
        setState(() {
          _startedAt = t;
          _elapsed = DateTime.now().difference(t);
        });
        _startTicker();
      }
    }
  }

  void _startTicker() {
    _tick?.cancel();
    _tick = Timer.periodic(const Duration(seconds: 1), (_) {
      if (_startedAt == null) return;
      setState(() {
        _elapsed = DateTime.now().difference(_startedAt!);
      });
    });
  }

  Future<void> _start() async {
    final now = DateTime.now();
    setState(() {
      _startedAt = now;
      _elapsed = Duration.zero;
    });
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_prefsKey, now.toIso8601String());
    _startTicker();
  }

  Future<void> _stop() async {
    _tick?.cancel();
    final minutes = _elapsed.inSeconds ~/ 60;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_prefsKey);
    setState(() {
      _startedAt = null;
      _elapsed = Duration.zero;
    });
    if (minutes < 1) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Less than a minute — nothing logged.')),
        );
      }
      return;
    }
    final repo = TicketsRepository(context.read<ApiClient>());
    try {
      await repo.logTime(
        widget.ticketId,
        minutes: minutes,
        description: _description,
        billable: _billable,
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Logged $minutes minute(s).')),
        );
        Navigator.of(context).pop(true);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Log failed: $e')),
        );
      }
    }
  }

  @override
  void dispose() {
    _tick?.cancel();
    super.dispose();
  }

  String _fmt(Duration d) {
    final h = d.inHours.toString().padLeft(2, '0');
    final m = (d.inMinutes % 60).toString().padLeft(2, '0');
    final s = (d.inSeconds % 60).toString().padLeft(2, '0');
    return '$h:$m:$s';
  }

  @override
  Widget build(BuildContext context) {
    final running = _startedAt != null;
    return Scaffold(
      appBar: AppBar(title: Text('Timer · #${widget.ticketId}')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const SizedBox(height: 24),
            Center(
              child: Text(
                _fmt(_elapsed),
                style: const TextStyle(
                  fontSize: 64,
                  fontFeatures: [FontFeature.tabularFigures()],
                ),
              ),
            ),
            const SizedBox(height: 32),
            TextField(
              enabled: !running,
              decoration: const InputDecoration(
                labelText: 'What are you working on?',
                border: OutlineInputBorder(),
              ),
              onChanged: (v) => _description = v,
            ),
            const SizedBox(height: 12),
            SwitchListTile.adaptive(
              title: const Text('Billable'),
              value: _billable,
              onChanged: running ? null : (v) => setState(() => _billable = v),
            ),
            const Spacer(),
            if (!running)
              FilledButton(
                onPressed: _start,
                style: FilledButton.styleFrom(
                  minimumSize: const Size.fromHeight(56),
                ),
                child: const Text('Start'),
              )
            else
              FilledButton(
                onPressed: _stop,
                style: FilledButton.styleFrom(
                  minimumSize: const Size.fromHeight(56),
                  backgroundColor: Colors.red,
                ),
                child: const Text('Stop & log'),
              ),
          ],
        ),
      ),
    );
  }
}
