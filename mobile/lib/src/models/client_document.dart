DateTime? _parseDate(dynamic v) {
  if (v == null) return null;
  if (v is DateTime) return v;
  return DateTime.tryParse(v.toString());
}

enum ClientDocumentKind { contract, warranty, diagram, welcome, other }

ClientDocumentKind _kindFromString(String? v) {
  switch (v) {
    case 'contract':
      return ClientDocumentKind.contract;
    case 'warranty':
      return ClientDocumentKind.warranty;
    case 'diagram':
      return ClientDocumentKind.diagram;
    case 'welcome':
      return ClientDocumentKind.welcome;
    default:
      return ClientDocumentKind.other;
  }
}

class ClientDocument {
  const ClientDocument({
    required this.id,
    required this.clientId,
    required this.title,
    required this.fileUrl,
    required this.kind,
    required this.clientVisible,
    required this.uploadedByEmail,
    required this.uploadedAt,
  });

  final int id;
  final int clientId;
  final String title;
  final String fileUrl;
  final ClientDocumentKind kind;
  final bool clientVisible;
  final String? uploadedByEmail;
  final DateTime? uploadedAt;

  factory ClientDocument.fromJson(Map<String, dynamic> json) =>
      ClientDocument(
        id: json['id'] as int,
        clientId: json['client'] as int? ?? 0,
        title: json['title'] as String? ?? '',
        fileUrl: json['file_url'] as String? ?? '',
        kind: _kindFromString(json['kind'] as String?),
        clientVisible: json['client_visible'] as bool? ?? true,
        uploadedByEmail: json['uploaded_by_email'] as String?,
        uploadedAt: _parseDate(json['uploaded_at']),
      );
}
