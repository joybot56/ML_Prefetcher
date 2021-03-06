import pandas as pd


class Vocab:
    def __init__(self, all_keys=None):
        self.key_to_val = {}
        self.val_to_key = {}
        self.counter = 0

        if all_keys is not None:
            for key in all_keys:
                self.add_key(key)

    def __len__(self):
        return self.counter

    def get_val(self, key):
        # Return `self.counter` by default to treat pruned out deltas 
        # as unknown. Assumption: all the keys remain the same, so we 
        # can use `self.counter` as a dummy value (kind of like [unk] 
        # in neural translation models).
        return self.key_to_val.get(key, self.counter)

    def get_key(self, val):
        return self.val_to_key.get(val, None)

    def add_key(self, key):
        if key not in self.key_to_val:
            self.key_to_val[key] = self.counter
            self.val_to_key[self.counter] = key
            self.counter += 1


def make_output_vocab(delta_out, num_output_deltas):
    return Vocab(
        delta_out.value_counts()
        .nlargest(num_output_deltas)
        .keys()
        .tolist()
    )


def build_vocabs(data, num_clusters=6, num_output_deltas=50000):
    pc_vocab = Vocab(data["pc"].drop_duplicates())

    delta_vocab = Vocab(
        data["delta_in"]
        .value_counts()  # Get how frequently each delta appears
        .loc[lambda count: count >= 10]  # Filter out uncommon input deltas
        .keys()  # Only keep the deltas
        .tolist()
    )

    # We need one output vocab per cluster for clustering LSTM, but only
    # one overall output vocab for embedding LSTM
    target_vocab = (
        [
            make_output_vocab(
                data.loc[data.cluster == cluster, "delta_out"],
                num_output_deltas
            )
            for cluster in range(num_clusters)
        ]
        if "cluster" in data
        else make_output_vocab(data["delta_out"], num_output_deltas)
    )

    return pc_vocab, delta_vocab, target_vocab
