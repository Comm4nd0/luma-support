import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../models/article.dart';
import '../repositories/knowledge_repository.dart';
import '../services/api_client.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../src/widgets/luma_icon.dart';

class KbListScreen extends StatefulWidget {
  const KbListScreen({super.key});

  @override
  State<KbListScreen> createState() => _KbListScreenState();
}

class _KbListScreenState extends State<KbListScreen> {
  late Future<List<Article>> _future;
  final _query = TextEditingController();

  KnowledgeRepository get _repo => KnowledgeRepository(context.read<ApiClient>());

  @override
  void initState() {
    super.initState();
    _future = _repo.list();
  }

  void _search() {
    setState(() => _future = _repo.list(q: _query.text.trim()));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Knowledge base')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: TextField(
              controller: _query,
              decoration: InputDecoration(
                hintText: 'Search articles',
                prefixIcon: const LumaIcon(PhosphorIconsDuotone.magnifyingGlass),
                suffixIcon: IconButton(
                  icon: const LumaIcon(PhosphorIconsDuotone.paperPlaneTilt),
                  onPressed: _search,
                ),
              ),
              onSubmitted: (_) => _search(),
            ),
          ),
          Expanded(
            child: FutureBuilder<List<Article>>(
              future: _future,
              builder: (context, snap) {
                if (snap.connectionState != ConnectionState.done) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snap.hasError) {
                  return Center(child: Text('Error: ${snap.error}'));
                }
                final items = snap.data ?? const <Article>[];
                if (items.isEmpty) {
                  return const Center(child: Text('No articles found.'));
                }
                return ListView.builder(
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  itemCount: items.length,
                  itemBuilder: (_, i) {
                    final a = items[i];
                    return Card(
                      margin: const EdgeInsets.only(bottom: 8),
                      child: ListTile(
                        onTap: () => context.push('/kb/${a.slug}'),
                        title: Text(a.title),
                        subtitle: Text(a.category),
                        trailing: const LumaIcon(PhosphorIconsDuotone.caretRight),
                      ),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
