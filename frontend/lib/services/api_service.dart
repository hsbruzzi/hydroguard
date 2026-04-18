import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/estado_model.dart';

class ApiService {
  // Para emulador Android, 10.0.2.2 apunta a tu máquina local.
  // En dispositivo físico, reemplazá por la IP local de tu PC.
  static const String baseUrl = 'http://10.0.2.2:8000';

  Future<EstadoModel> fetchEstado() async {
    final response = await http.get(Uri.parse('$baseUrl/estado'));

    if (response.statusCode != 200) {
      throw Exception('No se pudo obtener el estado actual');
    }

    final json = jsonDecode(response.body) as Map<String, dynamic>;
    return EstadoModel.fromJson(json);
  }
}
