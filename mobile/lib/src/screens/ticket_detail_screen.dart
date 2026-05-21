import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../models/ticket.dart';
import '../models/ticket_tag.dart';
import '../repositories/tickets_repository.dart';
import 'widgets/ticket_tile.dart';
import '../services/api_client.dart';
import '../services/current_user.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../src/widgets/luma_icon.dart';
import 'signature_screen.dart';
import 'ticket_timer_screen.dart';

class TicketDetailScreen extends StatefulWidget {
  const TicketDetailScreen({super.key, required this.ticketId});

  final int ticketId;

  @override
  State<TicketDetailScreen> createState() => _TicketDetailScreenState();
}

class _TicketDetailScreenState extends State<TicketDetailScreen> {
  late Future<Ticket> _future;

  TicketsRepository get _repo => TicketsRepository(context.read<ApiClient>());

  @override
  void initState() {
    super.initState();
    _future = _repo.get(widget.ticketId);
  }

  void _refresh() {
    setState(() {
      _future = _repo.get(widget.ticketId);
    });
  }

  Future<void> _setStatus(TicketStatus status) async {
    await _repo.setStatus(widget.ticketId, status);
    _refresh();
  }

  Future<void> _logTime() async {
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => const _LogTimeDialog(),
    );
    if (result == null) return;
    await _repo.logTime(
      widget.ticketId,
      minutes: result['minutes'] as int,
      description: result['description'] as String,
    );
    _refresh();
  }

  Future<void> _addNote() async {
    final isStaff = context.read<CurrentUser>().isStaff;
    final result = await showDialog<_NoteDialogResult>(
      context: context,
      builder: (_) => _NoteDialog(allowInternal: isStaff),
    );
    if (result == null || result.body.trim().isEmpty) return;
    await _repo.addNote(widget.ticketId, result.body.trim(),
        internal: result.internal);
    _refresh();
  }

  Future<void> _draftReply() async {
    final messenger = ScaffoldMessenger.of(context);
    setState(() {});
    try {
      final draft = await _repo.draftReply(widget.ticketId);
      if (!mounted) return;
      if (draft.isEmpty) {
        messenger.showSnackBar(
          const SnackBar(content: Text('AI drafting is disabled on this server.')),
        );
        return;
      }
      final result = await showDialog<_NoteDialogResult>(
        context: context,
        builder: (_) => _NoteDialog(
          initial: draft,
          title: 'AI draft (editable)',
          allowInternal: true,
        ),
      );
      if (result == null || result.body.trim().isEmpty) return;
      await _repo.addNote(widget.ticketId, result.body.trim(),
          internal: result.internal);
      _refresh();
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Draft failed: $e')));
    }
  }

  Future<void> _runTimer() async {
    final logged = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => TicketTimerScreen(ticketId: widget.ticketId),
      ),
    );
    if (logged == true) _refresh();
  }

  Future<void> _attachPhoto({required ImageSource source}) async {
    final picker = ImagePicker();
    final picked = await picker.pickImage(source: source, imageQuality: 80);
    if (picked == null) return;
    try {
      await _repo.uploadAttachment(widget.ticketId, File(picked.path));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Photo uploaded.')),
        );
        _refresh();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Upload failed: $e')),
        );
      }
    }
  }

  Future<void> _photoSheet() async {
    final source = await showModalBottomSheet<ImageSource>(
      context: context,
      builder: (_) => SafeArea(
        child: Wrap(
          children: [
            ListTile(
              leading: const Icon(Icons.camera_alt_outlined),
              title: const Text('Take a photo'),
              onTap: () => Navigator.pop(context, ImageSource.camera),
            ),
            ListTile(
              leading: const Icon(Icons.photo_library_outlined),
              title: const Text('Pick from gallery'),
              onTap: () => Navigator.pop(context, ImageSource.gallery),
            ),
          ],
        ),
      ),
    );
    if (source != null) await _attachPhoto(source: source);
  }

  Future<void> _editTags(Ticket ticket) async {
    final all = await _repo.listTags();
    if (!mounted) return;
    final initial = ticket.tags.map((t) => t.id).toSet();
    final selected = await showModalBottomSheet<Set<int>>(
      context: context,
      builder: (_) => _TagPicker(allTags: all, initial: initial),
      isScrollControlled: true,
    );
    if (selected == null) return;
    await _repo.setTags(ticket.id, selected.toList());
    _refresh();
  }

  Future<void> _captureSignature() async {
    final uploaded = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => SignatureScreen(ticketId: widget.ticketId),
      ),
    );
    if (uploaded == true) _refresh();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Ticket #${widget.ticketId}')),
      body: FutureBuilder<Ticket>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return Center(child: Text('Error: ${snap.error}'));
          }
          final t = snap.data!;
          final isStaff = context.watch<CurrentUser>().isStaff;
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text(t.subject,
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
              const SizedBox(height: 6),
              Text('${t.clientName} · ${t.priority.name} · ${t.status.name}'),
              if (t.isPaused) ...[
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: Colors.white12,
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: const [
                      Icon(Icons.pause_circle_outline, size: 16),
                      SizedBox(width: 6),
                      Text(
                        'SLA paused — waiting on client',
                        style: TextStyle(fontSize: 12),
                      ),
                    ],
                  ),
                ),
              ] else if (t.isBreached) ...[
                const SizedBox(height: 8),
                const Text(
                  'SLA breached',
                  style: TextStyle(color: Colors.redAccent, fontWeight: FontWeight.w600),
                ),
              ],
              const SizedBox(height: 12),
              if (t.tags.isNotEmpty || isStaff) ...[
                Row(
                  children: [
                    Expanded(
                      child: Wrap(
                        spacing: 6,
                        runSpacing: 6,
                        children: [
                          for (final tag in t.tags) _TagBadge(tag: tag),
                          if (t.tags.isEmpty)
                            const Text(
                              'No tags',
                              style: TextStyle(fontSize: 12, color: Colors.white54),
                            ),
                        ],
                      ),
                    ),
                    if (isStaff)
                      IconButton(
                        tooltip: 'Edit tags',
                        icon: const Icon(Icons.local_offer_outlined, size: 18),
                        onPressed: () => _editTags(t),
                      ),
                  ],
                ),
                const SizedBox(height: 12),
              ],
              Text(t.description, style: const TextStyle(height: 1.5)),
              if (t.csat != null && t.csat!.hasRating) ...[
                const SizedBox(height: 16),
                _CsatCard(csat: t.csat!),
              ],
              const SizedBox(height: 24),
              if (isStaff) ...[
                Wrap(
                  spacing: 8,
                  children: [
                    for (final s in const [
                      TicketStatus.assigned,
                      TicketStatus.inProgress,
                      TicketStatus.waiting,
                      TicketStatus.resolved,
                      TicketStatus.closed,
                    ])
                      OutlinedButton(
                        onPressed: () => _setStatus(s),
                        child: Text(statusToWire(s).replaceAll('_', ' ')),
                      ),
                  ],
                ),
                const SizedBox(height: 16),
              ],
              Row(
                children: [
                  if (isStaff) ...[
                    Expanded(
                      child: ElevatedButton.icon(
                        onPressed: _logTime,
                        icon: const LumaIcon(PhosphorIconsDuotone.timer),
                        label: const Text('Log time'),
                      ),
                    ),
                    const SizedBox(width: 8),
                  ],
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: _addNote,
                      icon: const LumaIcon(PhosphorIconsDuotone.notePencil),
                      label: const Text('Add note'),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  if (isStaff) ...[
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: _runTimer,
                        icon: const Icon(Icons.timer_outlined),
                        label: const Text('Start timer'),
                      ),
                    ),
                    const SizedBox(width: 8),
                  ],
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: _photoSheet,
                      icon: const Icon(Icons.photo_camera_outlined),
                      label: const Text('Photo'),
                    ),
                  ),
                ],
              ),
              if (isStaff) ...[
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  onPressed: _captureSignature,
                  icon: const Icon(Icons.gesture),
                  label: const Text('Capture signature'),
                ),
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  onPressed: _draftReply,
                  icon: const Icon(Icons.auto_awesome_outlined),
                  label: const Text('Draft reply with AI'),
                ),
              ],
            ],
          );
        },
      ),
    );
  }
}

class _LogTimeDialog extends StatefulWidget {
  const _LogTimeDialog();

  @override
  State<_LogTimeDialog> createState() => _LogTimeDialogState();
}

class _LogTimeDialogState extends State<_LogTimeDialog> {
  final _minutes = TextEditingController();
  final _description = TextEditingController();

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Log time'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          TextField(
            controller: _minutes,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(labelText: 'Minutes'),
          ),
          TextField(
            controller: _description,
            decoration: const InputDecoration(labelText: 'Description'),
          ),
        ],
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        ElevatedButton(
          onPressed: () {
            final m = int.tryParse(_minutes.text) ?? 0;
            if (m <= 0) return;
            Navigator.pop(context, {
              'minutes': m,
              'description': _description.text,
            });
          },
          child: const Text('Save'),
        ),
      ],
    );
  }
}

class _NoteDialogResult {
  const _NoteDialogResult({required this.body, required this.internal});
  final String body;
  final bool internal;
}

class _NoteDialog extends StatefulWidget {
  const _NoteDialog({this.initial, this.title, this.allowInternal = false});

  final String? initial;
  final String? title;
  final bool allowInternal;

  @override
  State<_NoteDialog> createState() => _NoteDialogState();
}

class _NoteDialogState extends State<_NoteDialog> {
  late final TextEditingController _body =
      TextEditingController(text: widget.initial ?? '');
  bool _internal = false;

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.title ?? 'Add note'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          TextField(
            controller: _body,
            maxLines: 6,
            decoration: const InputDecoration(labelText: 'Note'),
          ),
          if (widget.allowInternal)
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              controlAffinity: ListTileControlAffinity.leading,
              value: _internal,
              onChanged: (v) => setState(() => _internal = v ?? false),
              title: const Text('Internal (staff only)'),
              subtitle: const Text(
                'Clients will not see this note on the ticket.',
              ),
            ),
        ],
      ),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        ElevatedButton(
          onPressed: () => Navigator.pop(
            context,
            _NoteDialogResult(body: _body.text, internal: _internal),
          ),
          child: const Text('Save'),
        ),
      ],
    );
  }
}

class _TagBadge extends StatelessWidget {
  const _TagBadge({required this.tag});

  final TicketTag tag;

  @override
  Widget build(BuildContext context) {
    final color = parseTagColor(tag.color);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: color.withOpacity(0.18),
        border: Border.all(color: color.withOpacity(0.4)),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        tag.name,
        style: TextStyle(fontSize: 11, color: color, fontWeight: FontWeight.w600),
      ),
    );
  }
}

class _TagPicker extends StatefulWidget {
  const _TagPicker({required this.allTags, required this.initial});

  final List<TicketTag> allTags;
  final Set<int> initial;

  @override
  State<_TagPicker> createState() => _TagPickerState();
}

class _TagPickerState extends State<_TagPicker> {
  late final Set<int> _selected = {...widget.initial};

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text('Tags', style: TextStyle(fontWeight: FontWeight.w600)),
            const SizedBox(height: 12),
            if (widget.allTags.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 12),
                child: Text(
                  'No tags defined yet. Add one from the admin or web portal.',
                  style: TextStyle(color: Colors.white60),
                ),
              )
            else
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final tag in widget.allTags)
                    FilterChip(
                      label: Text(tag.name),
                      selected: _selected.contains(tag.id),
                      onSelected: (on) => setState(() {
                        if (on) {
                          _selected.add(tag.id);
                        } else {
                          _selected.remove(tag.id);
                        }
                      }),
                      selectedColor:
                          parseTagColor(tag.color).withOpacity(0.25),
                      checkmarkColor: parseTagColor(tag.color),
                    ),
                ],
              ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Cancel'),
                ),
                const SizedBox(width: 8),
                ElevatedButton(
                  onPressed: () => Navigator.pop(context, _selected),
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

class _CsatCard extends StatelessWidget {
  const _CsatCard({required this.csat});

  final CsatResponse csat;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Customer rating',
              style: TextStyle(fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 8),
            Text(
              '${csat.rating} / 5',
              style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700),
            ),
            if (csat.comment.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(csat.comment),
            ],
          ],
        ),
      ),
    );
  }
}
