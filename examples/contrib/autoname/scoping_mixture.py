# Copyright (c) 2017-2019 Uber Technologies, Inc.
# SPDX-License-Identifier: Apache-2.0

import argparse

import torch
from torch.distributions import constraints

import pyro
import pyro.distributions as dist
import pyro.optim
from pyro.contrib.autoname import scope
from pyro.infer import SVI, TraceEnum_ELBO, config_enumerate


def model(K, data):
    # Global parameters.
    weights = pyro.param("weights", torch.ones(K) / K, constraint=constraints.simplex)
    locs = pyro.param("locs", 10 * torch.randn(K))
    scale = pyro.param("scale", torch.tensor(0.5), constraint=constraints.positive)

    with pyro.plate("data"):
        return local_model(weights, locs, scale, data)


@scope(prefix="local")
def local_model(weights, locs, scale, data):
    assignment = pyro.sample(
        "assignment", dist.Categorical(weights).expand_by([len(data)])
    )
    return pyro.sample("obs", dist.Normal(locs[assignment], scale), obs=data)


def guide(K, data):
    assignment_probs = pyro.param(
        "assignment_probs",
        torch.ones(len(data), K) / K,
        constraint=constraints.unit_interval,
    )
    with pyro.plate("data"):
        return local_guide(assignment_probs)


@scope(prefix="local")
def local_guide(probs):
    return pyro.sample("assignment", dist.Categorical(probs))


def main(args):
    pyro.set_rng_seed(0)
    pyro.clear_param_store()
    K = 2

    data = torch.tensor([0.0, 1.0, 2.0, 20.0, 30.0, 40.0])
    optim = pyro.optim.Adam({"lr": 0.1})
    inference = SVI(
        model, config_enumerate(guide), optim, loss=TraceEnum_ELBO(max_plate_nesting=1)
    )

    print("Step\tLoss")
    loss = 0.0
    for step in range(args.num_epochs):
        if step and step % 10 == 0:
            print("{}\t{:0.5g}".format(step, loss))
            loss = 0.0
        loss += inference.step(K, data)

    print("Parameters:")
    for name, value in sorted(pyro.get_param_store().items()):
        print("{} = {}".format(name, value.detach().cpu().numpy()))


if __name__ == "__main__":
    assert pyro.__version__.startswith("1.8.3")
    parser = argparse.ArgumentParser(description="parse args")
    parser.add_argument("-n", "--num-epochs", default=200, type=int)
    args = parser.parse_args()
    main(args)
