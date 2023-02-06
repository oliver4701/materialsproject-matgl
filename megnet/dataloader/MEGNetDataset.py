"""
Tools to construct a dataloader for DGL grphs
"""
import os

import dgl
import torch
from dgl.data import DGLDataset
from dgl.data.utils import load_graphs, save_graphs
from pymatgen.core import Structure
from torch.utils.data import DataLoader
from tqdm import trange

from megnet.graph.compute import compute_pair_vector_and_distance
from megnet.layers.bond_expansion import BondExpansion


def _collate_fn(batch):
    """
    Merge a list of dgl graphs to form a batch
    """
    graphs, labels, graph_attr = map(list, zip(*batch))
    g = dgl.batch(graphs)
    labels = torch.tensor(labels, dtype=torch.float32)
    graph_attr = torch.stack(graph_attr)
    return g, labels, graph_attr


def MEGNetDataLoader(train_data, val_data, test_data, collate_fn, batch_size, num_workers):
    """
    Dataloader for MEGNet training
    Args:
    train_data: training data
    val_data: validation data
    test_data: testing data
    collate_fn:
    """
    train_loader = DataLoader(
        train_data,
        batch_size=batch_size,
        shuffle=True,
        collate_fn=collate_fn,
        num_workers=num_workers,
        pin_memory=True,
    )

    val_loader = DataLoader(
        val_data,
        batch_size=batch_size,
        shuffle=False,
        collate_fn=collate_fn,
        num_workers=num_workers,
        pin_memory=True,
    )

    test_loader = DataLoader(
        test_data,
        batch_size=batch_size,
        shuffle=False,
        collate_fn=collate_fn,
        num_workers=num_workers,
        pin_memory=True,
    )
    return train_loader, val_loader, test_loader


class MEGNetDataset(DGLDataset):
    """
    Create a dataset including dgl graphs
    """

    def __init__(self, structures, labels, label_name, converter, initial, final, num_centers, width):
        """
        Args:
        structures: Pymatgen strutcure
        labels: property values
        label: label name
        converter: Pmg2Graph converter
        """
        self.converter = converter
        self.structures = structures
        self.labels = torch.FloatTensor(labels)
        self.label_name = label_name
        self.initial = initial
        self.final = final
        self.num_centers = num_centers
        self.width = width
        super().__init__(name="MEGNetDataset")

    def has_cache(self, filename="dgl_graph.bin"):
        """
        Check if the dgl_graph.bin exists or not
        Args:
        :filename: Name of file storing dgl graphs
        """
        graph_path = os.path.join(os.getcwd(), filename)
        return os.path.exists(graph_path)

    def process(self):
        """
        Convert Pymatgen structure into dgl graphs
        """
        num_graphs = self.labels.shape[0]
        self.graphs = []
        self.graph_attr = []
        bond_expansion = BondExpansion(
            rbf_type="Gaussian", initial=self.initial, final=self.final, num_centers=self.num_centers, width=self.width
        )
        for idx in trange(num_graphs):
            structure = self.structures[idx]
            if isinstance(structure, Structure):
                graph, state_attr = self.converter.get_graph_from_structure(structure=structure)
            else:
                graph, state_attr = self.converter.get_graph_from_molecule(mol=structure)
            bond_vec, bond_dist = compute_pair_vector_and_distance(graph)
            graph.edata["edge_attr"] = bond_expansion(bond_dist)
            self.graphs.append(graph)
            self.graph_attr.append(state_attr)
        self.graph_attr = torch.tensor(self.graph_attr)

        return self.graphs, self.graph_attr

    def save(self, filename="dgl_graph.bin", filename_graph_attr="graph_attr.pt"):
        """
        Save dgl graphs
        Args:
        :filename: Name of file storing dgl graphs
        :filename_graph_attr: Name of file storing graph attrs
        """
        graph_path = os.path.join(os.getcwd(), filename)
        labels_with_key = {self.label_name: self.labels}
        save_graphs(graph_path, self.graphs, labels_with_key)
        torch.save(self.graph_attr, filename_graph_attr)

    def load(self, filename="dgl_graph.bin", filename_graph_attr="graph_attr.pt"):
        """
        Load dgl graphs
        Args:
        :filename: Name of file storing dgl graphs
        """
        graph_path = os.path.join(os.getcwd(), filename)
        self.graphs, label_dict = load_graphs(graph_path)
        self.label = torch.stack([label_dict[key] for key in self.label_keys], dim=1)
        self.graph_attr = torch.load("graph_attr.pt")

    def __getitem__(self, idx):
        """
        Get graph and label with idx
        """
        return self.graphs[idx], self.labels[idx], self.graph_attr[idx]

    def __len__(self):
        """
        Get size of dataset
        """
        return len(self.graphs)