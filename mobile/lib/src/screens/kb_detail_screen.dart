import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:provider/provider.dart';

import '../models/article.dart';
import '../repositories/knowledge_repository.dart';
import '../services/api_client.dart';

class KbDetailScreen extends StatefulWidget {
  const KbDetailScreen({super.key, required this.slug});

  final String slug;

  @override
  State<KbDetailScreen> createState() => _KbDetailScreenState();
}

class _KbDetailScreenState extends State<KbDetailScreen> {
  late Future<Article> _future;

  @override
  void initState() {
    super.initState();
    _future = KnowledgeRepository(context.read<ApiClient>()).get(widget.slug);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Article')),
      body: FutureBuilder<Article>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return Center(child: Text('Error: ${snap.error}'));
          }
          final a = snap.data!;
          return Markdown(
            padding: const EdgeInsets.all(16),
            data: '# ${a.title}\n\n*${a.category}*\n\n${a.content}',
            selectable: true,
          );
        },
      ),
    );
  }
}
