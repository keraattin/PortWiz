FROM golang:1.23-alpine AS build
WORKDIR /src
COPY go.mod ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -trimpath -o /out/portwiz-agent ./cmd/agent

FROM alpine:3.20
# nmap enables optional `-sV` service/version detection (the hybrid engine).
RUN apk add --no-cache ca-certificates nmap
COPY --from=build /out/portwiz-agent /usr/local/bin/portwiz-agent

# Run unprivileged. Connect-mode scanning needs no capabilities; SYN scanning
# (naabu -sS, a later milestone) needs CAP_NET_RAW, which the operator grants
# explicitly at run time (docker run --cap-add=NET_RAW) rather than running as
# root. nmap -sV over TCP connect works fine unprivileged.
RUN addgroup -S portwiz && adduser -S -G portwiz -u 10001 portwiz
USER portwiz

ENTRYPOINT ["/usr/local/bin/portwiz-agent"]
