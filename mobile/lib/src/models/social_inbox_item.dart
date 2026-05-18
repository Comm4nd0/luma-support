/// A DM / mention / comment surfaced from one of Luma's social
/// accounts. The mobile inbox screen lists these with age + actions.
class SocialInboxItem {
  SocialInboxItem({
    required this.id,
    required this.accountPlatform,
    required this.accountDisplay,
    required this.kind,
    required this.kindDisplay,
    required this.authorHandle,
    required this.authorDisplay,
    required this.preview,
    required this.permalink,
    required this.receivedAt,
    required this.status,
    required this.convertedTicketId,
  });

  final int id;
  final String accountPlatform;
  final String accountDisplay;
  final String kind;
  final String kindDisplay;
  final String authorHandle;
  final String authorDisplay;
  final String preview;
  final String permalink;
  final DateTime? receivedAt;
  final String status;
  final int? convertedTicketId;

  factory SocialInboxItem.fromJson(Map<String, dynamic> json) => SocialInboxItem(
        id: (json['id'] as num).toInt(),
        accountPlatform: json['account_platform'] as String? ?? '',
        accountDisplay: json['account_display'] as String? ?? '',
        kind: json['kind'] as String? ?? '',
        kindDisplay: json['kind_display'] as String? ?? '',
        authorHandle: json['author_handle'] as String? ?? '',
        authorDisplay: json['author_display'] as String? ?? '',
        preview: json['preview'] as String? ?? '',
        permalink: json['permalink'] as String? ?? '',
        receivedAt: json['received_at'] == null
            ? null
            : DateTime.tryParse(json['received_at'] as String),
        status: json['status'] as String? ?? 'open',
        convertedTicketId: (json['converted_ticket'] as num?)?.toInt(),
      );
}
