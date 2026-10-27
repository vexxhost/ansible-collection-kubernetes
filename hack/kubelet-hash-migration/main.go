// Copyright (c) 2026 VEXXHOST, Inc.
// SPDX-License-Identifier: Apache-2.0

// Command kubelet-hash-migration checks the container hash migration in
// plugins/module_utils/kubelet_hash_migration.py against a real containerd
// metadata database.
//
// "create" uses containerd's metadata store to write 300 Kubernetes-style
// containers with old hash annotations of different lengths, including
// records sized around protobuf length boundaries and large enough for
// BoltDB overflow pages, and writes the expected migrations to a plan file.
// "verify" runs bbolt's consistency check and reads every container back
// through containerd's metadata store, checking the new hashes.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"math/rand"
	"os"
	"strings"

	"github.com/containerd/containerd/v2/core/containers"
	"github.com/containerd/containerd/v2/core/metadata"
	"github.com/containerd/containerd/v2/pkg/namespaces"
	"github.com/containerd/typeurl/v2"
	bolt "go.etcd.io/bbolt"
	"google.golang.org/protobuf/types/known/anypb"
)

const ext = "io.cri-containerd.container.metadata"

type entry struct {
	ID      string `json:"id"`
	OldHash string `json:"old_hash"`
	NewHash string `json:"new_hash"`
}

func hexHash(r *rand.Rand, length int) string {
	for {
		s := fmt.Sprintf("%x", r.Uint32())
		if len(s) == length {
			return s
		}
	}
}

func metadataJSON(id, hash string, size int) []byte {
	build := func(pad string) []byte {
		b, _ := json.Marshal(map[string]any{
			"Version":  "v1",
			"Metadata": map[string]any{"ID": id, "Config": map[string]any{"annotations": map[string]string{"io.kubernetes.container.hash": hash}, "pad": pad}},
		})
		return b
	}
	b := build("")
	if size > len(b) {
		b = build(strings.Repeat("x", size-len(b)))
	}
	return b
}

func main() {
	mode, path, planPath := os.Args[1], os.Args[2], os.Args[3]
	bdb, err := bolt.Open(path, 0600, nil)
	if err != nil {
		panic(err)
	}
	defer bdb.Close()
	db := metadata.NewDB(bdb, nil, nil)
	ctx := namespaces.WithNamespace(context.Background(), "k8s.io")
	store := metadata.NewContainerStore(db)

	switch mode {
	case "create":
		if err := db.Init(context.Background()); err != nil {
			panic(err)
		}
		r := rand.New(rand.NewSource(1))
		var plan []entry
		sizes := map[int]int{10: 126, 11: 127, 12: 128, 13: 16382, 14: 16383, 15: 20000}
		for i := 0; i < 300; i++ {
			oldLen, newLen := 8, 8
			switch i % 5 {
			case 1:
				oldLen = 7
			case 2:
				newLen = 7
			case 3:
				oldLen, newLen = 6, 8
			}
			e := entry{ID: fmt.Sprintf("c%04d", i), OldHash: hexHash(r, oldLen), NewHash: hexHash(r, newLen)}
			plan = append(plan, e)
			meta := metadataJSON(e.ID, e.OldHash, sizes[i])
			spec := []byte(fmt.Sprintf(`{"ociVersion":"1.2.0","annotations":{"io.kubernetes.container.hash":"%s"}}`, e.OldHash))
			c := containers.Container{
				ID:         e.ID,
				Runtime:    containers.RuntimeInfo{Name: "io.containerd.runc.v2"},
				Spec:       &anypb.Any{TypeUrl: "types.containerd.io/opencontainers/runtime-spec/1/Spec", Value: spec},
				Extensions: map[string]typeurl.Any{ext: &anypb.Any{TypeUrl: "github.com/containerd/cri/pkg/store/container/Metadata", Value: meta}},
				Labels:     map[string]string{"io.kubernetes.container.name": e.ID},
			}
			if _, err := store.Create(ctx, c); err != nil {
				panic(err)
			}
		}
		out, _ := json.Marshal(plan)
		os.WriteFile(planPath, out, 0644)
	case "verify":
		var plan []entry
		raw, _ := os.ReadFile(planPath)
		json.Unmarshal(raw, &plan)
		if err := bdb.View(func(tx *bolt.Tx) error {
			for err := range tx.Check() {
				return err
			}
			return nil
		}); err != nil {
			panic(fmt.Sprintf("bbolt check failed: %v", err))
		}
		list, err := store.List(ctx)
		if err != nil {
			panic(err)
		}
		byID := map[string]containers.Container{}
		for _, c := range list {
			byID[c.ID] = c
		}
		bad := 0
		for _, e := range plan {
			c, ok := byID[e.ID]
			if !ok {
				bad++
				fmt.Println("missing", e.ID)
				continue
			}
			want := fmt.Sprintf(`"io.kubernetes.container.hash":"%s"`, e.NewHash)
			m := string(c.Extensions[ext].GetValue())
			s := string(c.Spec.GetValue())
			var parsed map[string]any
			if !strings.Contains(m, want) || !strings.Contains(s, want) || json.Unmarshal([]byte(m), &parsed) != nil {
				bad++
				fmt.Println("bad", e.ID)
			}
		}
		fmt.Printf("verified %d containers, %d bad\n", len(plan), bad)
	}
}
