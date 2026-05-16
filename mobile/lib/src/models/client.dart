import 'contact.dart';
import 'system.dart';

class Client {
  Client({
    required this.id,
    required this.name,
    required this.company,
    required this.email,
    required this.phone,
    required this.carePlanTier,
    required this.systems,
    required this.contacts,
    required this.openTicketCount,
    this.customerType = 'home',
    this.address = '',
    this.billingAddress = '',
    this.vatNumber = '',
    this.notes = '',
  });

  final int id;
  final String name;
  final String company;
  final String email;
  final String phone;
  final String carePlanTier;
  final List<ClientSystem> systems;
  final List<Contact> contacts;
  final int openTicketCount;
  final String customerType;
  final String address;
  final String billingAddress;
  final String vatNumber;
  final String notes;

  factory Client.fromJson(Map<String, dynamic> json) => Client(
        id: json['id'] as int,
        name: json['name'] as String? ?? '',
        company: json['company'] as String? ?? '',
        email: json['email'] as String? ?? '',
        phone: json['phone'] as String? ?? '',
        carePlanTier: json['care_plan_tier'] as String? ?? 'none',
        systems: (json['systems'] as List? ?? const [])
            .map((j) => ClientSystem.fromJson(j as Map<String, dynamic>))
            .toList(),
        contacts: (json['contacts'] as List? ?? const [])
            .map((j) => Contact.fromJson(j as Map<String, dynamic>))
            .toList(),
        openTicketCount: json['open_ticket_count'] as int? ?? 0,
        customerType: json['customer_type'] as String? ?? 'home',
        address: json['address'] as String? ?? '',
        billingAddress: json['billing_address'] as String? ?? '',
        vatNumber: json['vat_number'] as String? ?? '',
        notes: json['notes'] as String? ?? '',
      );
}
