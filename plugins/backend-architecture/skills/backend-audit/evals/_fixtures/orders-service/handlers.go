package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strings"

	"github.com/segmentio/kafka-go"
)

type Server struct {
	db     *sql.DB
	events *kafka.Writer
	pay    *PaymentClient
}

type CreateOrderReq struct {
	UserID     int64  `json:"user_id"`
	ProductID  int64  `json:"product_id"`
	Qty        int    `json:"qty"`
	CardNumber string `json:"card_number"`
	Email      string `json:"email"`
}

func (s *Server) CreateOrder(w http.ResponseWriter, r *http.Request) {
	var req CreateOrderReq
	json.NewDecoder(r.Body).Decode(&req)
	log.Printf("create order request: %+v", req)

	// check stock
	var stock int
	s.db.QueryRow("SELECT stock FROM products WHERE id = $1", req.ProductID).Scan(&stock)
	if stock < req.Qty {
		http.Error(w, "out of stock", 409)
		return
	}
	s.db.Exec("UPDATE products SET stock = $1 WHERE id = $2", stock-req.Qty, req.ProductID)

	var orderID int64
	err := s.db.QueryRow("INSERT INTO orders(user_id, product_id, qty, status) VALUES($1,$2,$3,'new') RETURNING id",
		req.UserID, req.ProductID, req.Qty).Scan(&orderID)
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}

	if err := s.pay.Charge(req.CardNumber, req.Qty*1000); err != nil {
		http.Error(w, "payment failed", 502)
		return
	}

	ev, _ := json.Marshal(map[string]any{"order_id": orderID, "type": "OrderPaid"})
	s.events.WriteMessages(context.Background(), kafka.Message{Value: ev})

	json.NewEncoder(w).Encode(map[string]any{"id": orderID})
}

func (s *Server) GetOrder(w http.ResponseWriter, r *http.Request) {
	id := strings.TrimPrefix(r.URL.Path, "/orders/")
	row := s.db.QueryRow("SELECT id, user_id, product_id, qty, status FROM orders WHERE id = $1", id)
	var o struct {
		ID, UserID, ProductID int64
		Qty                   int
		Status                string
	}
	if err := row.Scan(&o.ID, &o.UserID, &o.ProductID, &o.Qty, &o.Status); err == sql.ErrNoRows {
		http.NotFound(w, r)
		return
	}
	json.NewEncoder(w).Encode(o)
}

func (s *Server) SearchOrders(w http.ResponseWriter, r *http.Request) {
	status := r.URL.Query().Get("status")
	q := fmt.Sprintf("SELECT id, user_id, status FROM orders WHERE status = '%s'", status)
	rows, err := s.db.Query(q)
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}
	defer rows.Close()
	var out []map[string]any
	for rows.Next() {
		var id, uid int64
		var st string
		rows.Scan(&id, &uid, &st)
		var items int
		s.db.QueryRow("SELECT count(*) FROM order_items WHERE order_id = $1", id).Scan(&items)
		out = append(out, map[string]any{"id": id, "user_id": uid, "status": st, "items": items})
	}
	json.NewEncoder(w).Encode(out)
}
