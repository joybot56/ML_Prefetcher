import torch
import torch.nn as nn
import torch.nn.functional as F


class ClusteringLSTM(nn.Module):
    def __init__(
        self,
        num_pc,
        num_input_delta,
        num_output_delta,
        embed_dim,
        hidden_dim,
        num_pred=10,  # how many predictions to return
        num_layers=2,  # number of LSTM layers
        dropout=0,  # probability with which to apply dropout
    ):
        super(ClusteringLSTM, self).__init__()

        # The concatenation of these two things will be the input to the LSTM
        self.pc_embed = nn.Embedding(num_pc, embed_dim)
        self.delta_embed = nn.Embedding(num_input_delta, embed_dim)

        self.lstm = nn.LSTM(
            embed_dim * 2,
            hidden_dim,
            num_layers,
            dropout=dropout,
        )

        self.cluster_networks = nn.ModuleList(
            [
                nn.Sequential(
                    nn.Linear(hidden_dim, num_outputs), 
                    nn.Dropout(p=dropout)
                )
                for num_outputs in num_output_delta
            ]
        )

        # Although the paper doesn't mention it, the output from the LSTM needs
        # to be converted to probabilities over the possible deltas.
        self.num_pred = num_pred

    def forward(self, X, lstm_state, target=None):
        # X is the tuple (pc's, deltas) where:
        #       pc's and deltas have shape (T,)
        # target is a tensor of the target deltas, has shape (T,)
        #       target might be None if we just want to predict
        # Returns loss, lstm output, and lstm state

        pc, delta, clusters = X
        batch_size = pc.shape[0]

        pc_embed = self.pc_embed(pc)
        delta_embed = self.delta_embed(delta)
        lstm_in = torch.cat([pc_embed, delta_embed], dim=-1)

        # Unsqueeze a dimension for `batch` (necessary for LSTM input)
        if len(lstm_in.shape) < 3:
            lstm_in = lstm_in.unsqueeze(dim=1)

        # Run the embeddings through the LSTM and get the top K predictions
        # (`topk` returns tuple of values and indices, the indices represent
        #  the deltas themselves and the values are their probabilities)
        lstm_out, state = self.lstm(lstm_in, lstm_state)

        # Create a mapping that tells us which input indices correspond to the 
        # inputs of each cluster.
        indices = [[] for _ in range(len(self.cluster_networks))]

        for orig, cluster in enumerate(clusters):
            indices[cluster.item()].append(orig)

        loss = 0
        outputs = torch.zeros(batch_size, self.num_pred, dtype=torch.long, device=pc.device)

        # Pick out the inputs corresponding to each cluster, and run *all* of
        # those inputs through the task-specific network at once.
        for cluster, network in enumerate(self.cluster_networks):
            orig_indices = indices[cluster]

            # If there are no inputs corresponding to this cluster in the
            # batch, just skip it to avoid errors computing loss.
            if len(orig_indices) == 0:
                continue

            inputs = lstm_out[orig_indices]
            output = network(inputs)
            probabilities = F.log_softmax(output, dim=-1).squeeze(dim=1)

            if target is not None:
                # Cross entropy loss (log softmax part was already performed)
                loss += F.nll_loss(probabilities, target[orig_indices])

            _, preds = torch.topk(probabilities, self.num_pred, sorted=False)
            outputs[orig_indices] = preds

        return loss, outputs, state

    def predict(self, X, lstm_state):
        with torch.no_grad():
            _, preds, state = self.forward(X, lstm_state)
            return preds, state


def test_net():
    pc = torch.arange(0, 4)  # [0, 1, 2, 3]
    delta = torch.arange(3, -1, -1)  # [3, 2, 1, 0]
    clusters = torch.arange(2, 6)  # [2, 3, 4, 5]
    target = torch.arange(0, 4)

    net = ClusteringLSTM(4, 4, [4] * 6, 10, 30, num_pred=2)

    print("Testing forward pass of clustering LSTM")
    loss, preds, state = net((pc, delta, clusters), None, target)
    loss, preds, state = net((pc, delta, clusters), state, target)

    print(loss)
    print(preds.shape)
    print(state[0].shape)  # hidden state
    print(state[1].shape)  # cell state

    print("\nTesting prediction of clustering LSTM")
    preds, state = net.predict((pc, delta, clusters), None)
    preds, state = net.predict((pc, delta, clusters), state)

    print(preds.shape)
    print(state[0].shape)  # hidden state
    print(state[1].shape)  # cell state


if __name__ == "__main__":
    test_net()
