FROM rust:1.75-slim AS builder
WORKDIR /app
COPY Cargo.toml Cargo.lock ./
COPY src ./src
RUN cargo build --release

FROM debian:bookworm-slim
WORKDIR /app
COPY --from=builder /app/target/release/solver_daemon /app/solver_daemon
EXPOSE 9998
CMD ["/app/solver_daemon"]
