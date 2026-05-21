class TicketTag {
  const TicketTag({
    required this.id,
    required this.name,
    required this.slug,
    required this.color,
  });

  final int id;
  final String name;
  final String slug;
  final String color;

  factory TicketTag.fromJson(Map<String, dynamic> json) => TicketTag(
        id: json['id'] as int,
        name: json['name'] as String? ?? '',
        slug: json['slug'] as String? ?? '',
        color: json['color'] as String? ?? '#14b8a6',
      );

  Map<String, dynamic> toCreateJson() => {
        'name': name,
        'color': color,
      };
}
