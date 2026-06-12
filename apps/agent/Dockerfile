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
ENTRYPOINT ["/usr/local/bin/portwiz-agent"]
