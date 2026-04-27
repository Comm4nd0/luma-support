import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import 'auth_service.dart';
import 'config.dart';

class ApiClient {
  ApiClient(this._auth);

  final AuthService _auth;

  Map<String, String> _headers({String? contentType = 'application/json'}) => {
        if (contentType != null) 'Content-Type': contentType,
        if (_auth.accessToken != null) 'Authorization': 'Bearer ${_auth.accessToken}',
      };

  Future<List<dynamic>> listTickets({String? status, String? priority}) async {
    final params = <String, String>{};
    if (status != null) params['status'] = status;
    if (priority != null) params['priority'] = priority;
    final uri = Uri.parse('$kApiBase/tickets/').replace(queryParameters: params);
    final res = await http.get(uri, headers: _headers());
    if (res.statusCode != 200) {
      throw Exception('Failed to list tickets: ${res.statusCode}');
    }
    final data = jsonDecode(res.body);
    return (data is Map && data.containsKey('results')) ? data['results'] as List : data as List;
  }

  Future<Map<String, dynamic>> getTicket(int id) async {
    final res = await http.get(
      Uri.parse('$kApiBase/tickets/$id/'),
      headers: _headers(),
    );
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> createTicket(Map<String, dynamic> body) async {
    final res = await http.post(
      Uri.parse('$kApiBase/tickets/'),
      headers: _headers(),
      body: jsonEncode(body),
    );
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<void> updateStatus(int ticketId, String status) async {
    await http.post(
      Uri.parse('$kApiBase/tickets/$ticketId/status/'),
      headers: _headers(),
      body: jsonEncode({'status': status}),
    );
  }

  Future<void> logTime(int ticketId, int minutes, String description,
      {bool billable = true}) async {
    await http.post(
      Uri.parse('$kApiBase/tickets/$ticketId/time/'),
      headers: _headers(),
      body: jsonEncode({
        'minutes': minutes,
        'description': description,
        'billable': billable,
      }),
    );
  }

  Future<void> addNote(int ticketId, String body, {bool internal = true}) async {
    await http.post(
      Uri.parse('$kApiBase/tickets/$ticketId/notes/'),
      headers: _headers(),
      body: jsonEncode({'body': body, 'internal': internal}),
    );
  }

  Future<void> uploadAttachment(int ticketId, File file) async {
    final req = http.MultipartRequest(
      'POST',
      Uri.parse('$kApiBase/tickets/$ticketId/attachments/'),
    );
    req.headers.addAll(_headers(contentType: null));
    req.files.add(await http.MultipartFile.fromPath('file', file.path));
    await req.send();
  }
}
