import 'dart:io';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../repositories/knowledge_repository.dart';
import '../repositories/tickets_repository.dart';
import '../services/api_client.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../src/widgets/luma_icon.dart';

class TicketCreateScreen extends StatefulWidget {
  const TicketCreateScreen({super.key});

  @override
  State<TicketCreateScreen> createState() => _TicketCreateScreenState();
}

class _TicketCreateScreenState extends State<TicketCreateScreen> {
  final _subject = TextEditingController();
  final _description = TextEditingController();
  final _clientId = TextEditingController();
  String _priority = 'medium';
  File? _photo;
  bool _busy = false;

  Future<void> _pickPhoto() async {
    final picker = ImagePicker();
    final f = await picker.pickImage(source: ImageSource.camera);
    if (f != null) setState(() => _photo = File(f.path));
  }

  Future<void> _suggestArticles() async {
    final subject = _subject.text.trim();
    final description = _description.text.trim();
    if (subject.isEmpty && description.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Type a subject or description first.'),
        ),
      );
      return;
    }
    setState(() => _busy = true);
    try {
      final repo = KnowledgeRepository(context.read<ApiClient>());
      final suggestions = await repo.suggest(
        subject: subject,
        description: description,
      );
      if (!mounted) return;
      if (suggestions.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('No matching articles — go ahead and file the ticket.'),
          ),
        );
        return;
      }
      await showModalBottomSheet<void>(
        context: context,
        showDragHandle: true,
        builder: (_) => SafeArea(
          child: ListView(
            shrinkWrap: true,
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            children: [
              const Padding(
                padding: EdgeInsets.only(bottom: 12),
                child: Text(
                  'Articles that might help',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                ),
              ),
              for (final s in suggestions)
                Card(
                  child: ListTile(
                    title: Text(s.title),
                    subtitle: Text(s.snippet),
                    onTap: () {
                      Navigator.pop(context);
                      context.push('/kb/${s.slug}');
                    },
                  ),
                ),
            ],
          ),
        ),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Suggestion lookup failed: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _submit() async {
    setState(() => _busy = true);
    try {
      final repo = TicketsRepository(context.read<ApiClient>());
      final created = await repo.create({
        'client': int.tryParse(_clientId.text) ?? 0,
        'subject': _subject.text.trim(),
        'description': _description.text.trim(),
        'priority': _priority,
      });
      if (_photo != null) {
        await repo.uploadAttachment(created.id, _photo!);
      }
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not create ticket: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('New ticket')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            controller: _clientId,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(labelText: 'Client ID'),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _subject,
            decoration: const InputDecoration(labelText: 'Subject'),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _description,
            maxLines: 4,
            decoration: const InputDecoration(labelText: 'Description'),
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(
            value: _priority,
            decoration: const InputDecoration(labelText: 'Priority'),
            items: const [
              DropdownMenuItem(value: 'critical', child: Text('Critical')),
              DropdownMenuItem(value: 'high', child: Text('High')),
              DropdownMenuItem(value: 'medium', child: Text('Medium')),
              DropdownMenuItem(value: 'low', child: Text('Low')),
            ],
            onChanged: (v) => setState(() => _priority = v ?? 'medium'),
          ),
          const SizedBox(height: 16),
          OutlinedButton.icon(
            onPressed: _pickPhoto,
            icon: const LumaIcon(PhosphorIconsDuotone.camera),
            label: Text(_photo == null ? 'Add photo' : 'Photo selected'),
          ),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: _busy ? null : _suggestArticles,
            icon: const Icon(Icons.lightbulb_outline),
            label: const Text('Suggest articles'),
          ),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: _busy ? null : _submit,
            child: _busy
                ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Create ticket'),
          ),
        ],
      ),
    );
  }
}
