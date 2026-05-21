class SavedTicketFilter {
  const SavedTicketFilter({
    required this.id,
    required this.name,
    required this.querystring,
    required this.pinned,
  });

  final int id;
  final String name;
  final String querystring;
  final bool pinned;

  /// Parse the saved querystring into a flat map for the ticket list's
  /// API call. Keys we know how to apply on mobile: status, priority,
  /// tag, tag_slug, client.
  Map<String, String> toParams() {
    final out = <String, String>{};
    for (final part in querystring.split('&')) {
      if (part.isEmpty) continue;
      final eq = part.indexOf('=');
      if (eq <= 0) continue;
      final k = Uri.decodeQueryComponent(part.substring(0, eq));
      final v = Uri.decodeQueryComponent(part.substring(eq + 1));
      out[k] = v;
    }
    return out;
  }

  factory SavedTicketFilter.fromJson(Map<String, dynamic> json) =>
      SavedTicketFilter(
        id: json['id'] as int,
        name: json['name'] as String? ?? '',
        querystring: json['querystring'] as String? ?? '',
        pinned: json['pinned'] as bool? ?? false,
      );
}
