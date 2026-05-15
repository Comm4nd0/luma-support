class ClientSystem {
  ClientSystem({
    required this.id,
    required this.clientId,
    required this.type,
    required this.name,
    required this.description,
    required this.monitoringUrl,
  });

  final int id;
  final int clientId;
  final String type;
  final String name;
  final String description;
  final String monitoringUrl;

  factory ClientSystem.fromJson(Map<String, dynamic> json) => ClientSystem(
        id: json['id'] as int,
        clientId: json['client'] as int? ?? 0,
        type: json['type'] as String? ?? '',
        name: json['name'] as String? ?? '',
        description: json['description'] as String? ?? '',
        monitoringUrl: json['monitoring_url'] as String? ?? '',
      );
}
