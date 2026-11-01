package main

import (
	"database/sql"
	"log"
	"net/http"

	_ "github.com/lib/pq"
	"github.com/segmentio/kafka-go"
)

func main() {
	db, err := sql.Open("postgres", "postgres://orders:orders123@db:5432/orders?sslmode=disable")
	if err != nil {
		log.Fatal(err)
	}
	writer := &kafka.Writer{Addr: kafka.TCP("kafka:9092"), Topic: "order-events"}
	s := &Server{db: db, events: writer, pay: NewPaymentClient("https://api.payprovider.example")}

	go RunShipmentConsumer(db)

	http.HandleFunc("/orders", s.CreateOrder)
	http.HandleFunc("/orders/", s.GetOrder)
	http.HandleFunc("/admin/orders/search", s.SearchOrders)
	log.Fatal(http.ListenAndServe(":8080", nil))
}
