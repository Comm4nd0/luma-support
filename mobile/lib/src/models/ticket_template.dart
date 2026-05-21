class TicketTemplate {
  const TicketTemplate({
    required this.id,
    required this.name,
    required this.body,
    required this.publicDefault,
  });

  final int id;
  final String name;
  final String body;
  final bool publicDefault;

  factory TicketTemplate.fromJson(Map<String, dynamic> json) => TicketTemplate(
        id: json['id'] as int,
        name: json['name'] as String? ?? '',
        body: json['body'] as String? ?? '',
        publicDefault: json['public_default'] as bool? ?? true,
      );
}
