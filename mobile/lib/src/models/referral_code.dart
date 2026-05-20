class ReferralReferral {
  ReferralReferral({
    required this.name,
    required this.stage,
    required this.stageDisplay,
    required this.createdAt,
  });

  final String name;
  final String stage;
  final String stageDisplay;
  final DateTime createdAt;

  factory ReferralReferral.fromJson(Map<String, dynamic> json) =>
      ReferralReferral(
        name: (json['name'] as String?) ?? '',
        stage: (json['stage'] as String?) ?? '',
        stageDisplay: (json['stage_display'] as String?) ?? '',
        createdAt:
            DateTime.tryParse(json['created_at'] as String? ?? '') ??
                DateTime.now(),
      );
}

class ReferralCode {
  ReferralCode({
    required this.code,
    required this.shareLink,
    required this.creditBalance,
    required this.lifetimeCredit,
    required this.referrals,
  });

  final String code;
  final String shareLink;
  final String creditBalance;
  final String lifetimeCredit;
  final List<ReferralReferral> referrals;

  factory ReferralCode.fromJson(Map<String, dynamic> json) => ReferralCode(
        code: (json['code'] as String?) ?? '',
        shareLink: (json['share_link'] as String?) ?? '',
        creditBalance: json['credit_balance']?.toString() ?? '0',
        lifetimeCredit: json['lifetime_credit']?.toString() ?? '0',
        referrals: (json['referrals'] as List? ?? const [])
            .map((j) => ReferralReferral.fromJson(j as Map<String, dynamic>))
            .toList(),
      );
}
