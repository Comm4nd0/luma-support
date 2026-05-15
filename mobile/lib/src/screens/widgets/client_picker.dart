import 'package:flutter/material.dart';

import '../../models/client.dart';
import '../../repositories/clients_repository.dart';
import '../../services/api_client.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../../src/widgets/luma_icon.dart';

/// Modal bottom sheet that lists clients and returns the one tapped.
/// Returns null if dismissed without a selection.
Future<Client?> showClientPicker(
  BuildContext context,
  ApiClient api,
) {
  return showModalBottomSheet<Client>(
    context: context,
    isScrollControlled: true,
    builder: (ctx) => _ClientPickerSheet(api: api),
  );
}

class _ClientPickerSheet extends StatefulWidget {
  const _ClientPickerSheet({required this.api});
  final ApiClient api;

  @override
  State<_ClientPickerSheet> createState() => _ClientPickerSheetState();
}

class _ClientPickerSheetState extends State<_ClientPickerSheet> {
  late Future<List<Client>> _future;
  String _filter = '';

  @override
  void initState() {
    super.initState();
    _future = ClientsRepository(widget.api).list();
  }

  @override
  Widget build(BuildContext context) {
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.7,
      maxChildSize: 0.95,
      minChildSize: 0.3,
      builder: (_, scroll) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
        child: Column(
          children: [
            const Text(
              'Pick a client',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 12),
            TextField(
              decoration: const InputDecoration(
                prefixIcon: LumaIcon(PhosphorIconsDuotone.magnifyingGlass),
                hintText: 'Filter…',
              ),
              onChanged: (v) => setState(() => _filter = v.toLowerCase()),
            ),
            const SizedBox(height: 8),
            Expanded(
              child: FutureBuilder<List<Client>>(
                future: _future,
                builder: (_, snap) {
                  if (snap.connectionState != ConnectionState.done) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  if (snap.hasError) {
                    return Center(child: Text('Error: ${snap.error}'));
                  }
                  final items = (snap.data ?? const <Client>[])
                      .where((c) =>
                          _filter.isEmpty ||
                          c.name.toLowerCase().contains(_filter) ||
                          c.company.toLowerCase().contains(_filter))
                      .toList();
                  if (items.isEmpty) {
                    return const Center(child: Text('No matches.'));
                  }
                  return ListView.builder(
                    controller: scroll,
                    itemCount: items.length,
                    itemBuilder: (_, i) {
                      final c = items[i];
                      return ListTile(
                        title: Text(c.name.isEmpty ? c.company : c.name),
                        subtitle: c.company.isEmpty || c.company == c.name
                            ? null
                            : Text(c.company),
                        onTap: () => Navigator.of(context).pop(c),
                      );
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
