class Article {
  Article({
    required this.id,
    required this.title,
    required this.slug,
    required this.content,
    required this.category,
    required this.clientVisible,
    required this.publishedAt,
  });

  final int id;
  final String title;
  final String slug;
  final String content;
  final String category;
  final bool clientVisible;
  final DateTime? publishedAt;

  factory Article.fromJson(Map<String, dynamic> json) => Article(
        id: json['id'] as int,
        title: json['title'] as String? ?? '',
        slug: json['slug'] as String? ?? '',
        content: json['content'] as String? ?? '',
        category: json['category'] as String? ?? 'general',
        clientVisible: json['client_visible'] as bool? ?? false,
        publishedAt: json['published_at'] == null
            ? null
            : DateTime.tryParse(json['published_at'] as String),
      );
}
