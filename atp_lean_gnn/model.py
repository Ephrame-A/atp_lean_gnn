from __future__ import annotations

from dataclasses import dataclass

import torch
import torch.nn.functional as F
from torch import nn
from torch_geometric.nn import SAGEConv, global_mean_pool

from .pyg import NODE_TYPE_TO_ID


@dataclass(frozen=True)
class GraphSAGEClassifierConfig:
    hidden_dim: int = 128
    num_layers: int = 4
    dropout: float = 0.2
    readout: str = "state"

    def to_dict(self) -> dict[str, object]:
        return {
            "hidden_dim": self.hidden_dim,
            "num_layers": self.num_layers,
            "dropout": self.dropout,
            "readout": self.readout,
        }


class GraphSAGEStateClassifier(nn.Module):
    def __init__(
        self,
        *,
        num_node_labels: int,
        num_tactics: int,
        num_node_types: int = len(NODE_TYPE_TO_ID),
        hidden_dim: int = 128,
        num_layers: int = 4,
        dropout: float = 0.2,
        use_node_type: bool = True,
        readout: str = "state",
    ) -> None:
        super().__init__()

        if num_layers < 1:
            raise ValueError("GraphSAGEStateClassifier requires at least one message-passing layer.")
        if readout not in {"state", "mean"}:
            raise ValueError("GraphSAGEStateClassifier readout must be either 'state' or 'mean'.")

        self.label_embedding = nn.Embedding(num_node_labels, hidden_dim)
        self.node_type_embedding = (
            nn.Embedding(num_node_types, hidden_dim) if use_node_type else None
        )
        self.convs = nn.ModuleList(
            SAGEConv(hidden_dim, hidden_dim) for _ in range(num_layers)
        )
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(hidden_dim, num_tactics)
        self.readout_mode = readout

    def encode_nodes(self, data) -> torch.Tensor:
        x = self.label_embedding(data.x)
        if self.node_type_embedding is not None:
            x = x + self.node_type_embedding(data.node_type)

        for index, conv in enumerate(self.convs):
            x = conv(x, data.edge_index)
            x = F.relu(x)
            if index < len(self.convs) - 1:
                x = self.dropout(x)
        return x

    def readout(self, node_embeddings: torch.Tensor, data) -> torch.Tensor:
        if self.readout_mode == "mean":
            if hasattr(data, "batch"):
                batch = data.batch.to(device=node_embeddings.device, dtype=torch.long)
            else:
                batch = torch.zeros(
                    node_embeddings.size(0),
                    device=node_embeddings.device,
                    dtype=torch.long,
                )
            return global_mean_pool(node_embeddings, batch)

        if not hasattr(data, "state_node_index"):
            raise ValueError("Batched graph data is missing the 'state_node_index' attribute.")

        state_node_index = data.state_node_index
        if not torch.is_tensor(state_node_index):
            state_node_index = torch.tensor(
                [int(state_node_index)],
                device=node_embeddings.device,
                dtype=torch.long,
            )
        else:
            state_node_index = state_node_index.to(
                device=node_embeddings.device,
                dtype=torch.long,
            ).view(-1)

        return node_embeddings.index_select(0, state_node_index)

    def forward(self, data) -> torch.Tensor:
        node_embeddings = self.encode_nodes(data)
        graph_embeddings = self.readout(node_embeddings, data)
        return self.classifier(self.dropout(graph_embeddings))
