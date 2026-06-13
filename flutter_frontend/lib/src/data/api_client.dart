import 'package:dio/dio.dart';

import '../config/app_config.dart';
import '../storage/session_storage.dart';
import 'api_exception.dart';

class ApiClient {
  ApiClient(this._sessionStorage)
      : _dio = Dio(
          BaseOptions(
            baseUrl: AppConfig.baseUrl,
            connectTimeout: const Duration(seconds: 10),
            receiveTimeout: const Duration(seconds: 20),
          ),
        ) {
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final session = await _sessionStorage.readSession();
          if (session != null) {
            options.headers['Authorization'] = 'Bearer ${session.token}';
          }
          handler.next(options);
        },
      ),
    );
  }

  final SessionStorage _sessionStorage;
  final Dio _dio;

  Future<T> get<T>(String path, {Map<String, dynamic>? query}) async {
    try {
      final response = await _dio.get<T>(path, queryParameters: query);
      return response.data as T;
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  Future<T> post<T>(String path, {Object? data}) async {
    try {
      final response = await _dio.post<T>(path, data: data);
      return response.data as T;
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  Future<T> put<T>(String path, {Object? data}) async {
    try {
      final response = await _dio.put<T>(path, data: data);
      return response.data as T;
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  Future<T> delete<T>(String path) async {
    try {
      final response = await _dio.delete<T>(path);
      return response.data as T;
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  ApiException _handleError(DioException error) {
    final status = error.response?.statusCode;
    final data = error.response?.data;
    final message = data is Map && data['detail'] is String
        ? data['detail'] as String
        : (error.message ?? 'Unexpected error');
    return ApiException(statusCode: status, message: message);
  }
}
