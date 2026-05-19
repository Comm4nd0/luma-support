/// Summary of one of Luma's connected social accounts. Returned both
/// inline on the dashboard-stats endpoint (for the KPI strip) and from
/// `/api/v1/social/accounts/` (for the management screen).
class SocialAccountSummary {
  SocialAccountSummary({
    required this.id,
    required this.platform,
    required this.platformDisplay,
    required this.displayName,
    required this.healthStatus,
    required this.followers,
    required this.followersDelta7d,
    required this.daysSinceLastPost,
    required this.lastError,
  });

  final int id;
  final String platform;
  final String platformDisplay;
  final String displayName;
  final String healthStatus;
  final int? followers;
  final int? followersDelta7d;
  final int? daysSinceLastPost;
  final String lastError;

  bool get isHealthy => healthStatus == 'ok' || healthStatus.isEmpty;

  factory SocialAccountSummary.fromJson(Map<String, dynamic> json) =>
      SocialAccountSummary(
        id: (json['id'] as num).toInt(),
        platform: json['platform'] as String? ?? '',
        platformDisplay: json['platform_display'] as String? ?? '',
        displayName: json['display_name'] as String? ?? '',
        healthStatus: json['health_status'] as String? ?? '',
        followers: (json['followers'] as num?)?.toInt(),
        followersDelta7d: (json['followers_delta_7d'] as num?)?.toInt(),
        daysSinceLastPost: (json['days_since_last_post'] as num?)?.toInt(),
        lastError: json['last_error'] as String? ?? '',
      );
}
