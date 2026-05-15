class Contact {
  Contact({
    required this.id,
    required this.clientId,
    required this.name,
    required this.email,
    required this.phone,
    required this.title,
    required this.isPrimary,
  });

  final int id;
  final int clientId;
  final String name;
  final String email;
  final String phone;
  final String title;
  final bool isPrimary;

  factory Contact.fromJson(Map<String, dynamic> json) => Contact(
        id: json['id'] as int,
        clientId: json['client'] as int? ?? 0,
        name: json['name'] as String? ?? '',
        email: json['email'] as String? ?? '',
        phone: json['phone'] as String? ?? '',
        title: json['title'] as String? ?? '',
        isPrimary: json['is_primary'] as bool? ?? false,
      );
}
