use solver_daemon::{evaluate_and_solve, SolverInput};
use tokio::io::{AsyncBufReadExt, AsyncReadExt, AsyncWriteExt, BufReader};
use tokio::net::{TcpListener, TcpStream};

/// Handles incoming connection supporting both raw TCP line-delimited JSON and HTTP REST
async fn handle_connection(mut stream: TcpStream) {
    let (reader, mut writer) = stream.split();
    let mut buf_reader = BufReader::new(reader);
    let mut first_line = String::new();

    if buf_reader.read_line(&mut first_line).await.is_err() || first_line.is_empty() {
        return;
    }

    // 1. HTTP Request Detection
    if first_line.starts_with("GET ") || first_line.starts_with("POST ") {
        if first_line.starts_with("GET /health") {
            let body = "{\"status\": \"healthy\", \"engine\": \"Rust DCFR Depth-Limited Engine\"}";
            let resp = format!(
                "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
                body.len(),
                body
            );
            let _ = writer.write_all(resp.as_bytes()).await;
            return;
        }

        // Read headers until empty line (\r\n or \n)
        let mut content_length: usize = 0;
        loop {
            let mut header_line = String::new();
            if buf_reader.read_line(&mut header_line).await.is_err() || header_line.trim().is_empty() {
                break;
            }
            let lower = header_line.to_lowercase();
            if lower.starts_with("content-length:") {
                if let Some(val) = header_line.split(':').nth(1) {
                    content_length = val.trim().parse().unwrap_or(0);
                }
            }
        }

        // Read exact body
        let mut body_bytes = vec![0u8; content_length];
        if content_length > 0 {
            let _ = buf_reader.read_exact(&mut body_bytes).await;
        }
        let body_str = String::from_utf8_lossy(&body_bytes);

        let output = match serde_json::from_str::<SolverInput>(&body_str) {
            Ok(input) => evaluate_and_solve(input),
            Err(err) => {
                let err_body = format!("{{\"error\": \"Invalid JSON: {}\"}}", err);
                let resp = format!(
                    "HTTP/1.1 400 Bad Request\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
                    err_body.len(),
                    err_body
                );
                let _ = writer.write_all(resp.as_bytes()).await;
                return;
            }
        };

        let out_str = serde_json::to_string(&output).unwrap_or_default();
        let resp = format!(
            "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
            out_str.len(),
            out_str
        );
        let _ = writer.write_all(resp.as_bytes()).await;
        return;
    }

    // 2. TCP Socket JSON (first_line is the complete line!)
    let output = match serde_json::from_str::<SolverInput>(&first_line) {
        Ok(input) => evaluate_and_solve(input),
        Err(err) => {
            let err_json = format!("{{\"error\": \"Failed to parse JSON: {}\"}}\n", err);
            let _ = writer.write_all(err_json.as_bytes()).await;
            return;
        }
    };

    if let Ok(res_str) = serde_json::to_string(&output) {
        let _ = writer.write_all(format!("{}\n", res_str).as_bytes()).await;
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let port = std::env::var("PORT").unwrap_or_else(|_| "9998".to_string());
    let addr = format!("0.0.0.0:{}", port);
    let listener = TcpListener::bind(&addr).await?;
    println!("Fast CFR Depth-Limited Solver daemon listening on {}", addr);

    loop {
        let (stream, _) = listener.accept().await?;
        tokio::spawn(async move {
            handle_connection(stream).await;
        });
    }
}
