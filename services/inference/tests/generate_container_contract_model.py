import argparse
from pathlib import Path

import onnx
from onnx import TensorProto, helper

from app.segmentation import INPUT_HEIGHT, INPUT_WIDTH


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a synthetic container contract model")
    parser.add_argument("destination", type=Path)
    parser.add_argument("--version", default="container-contract-only")
    arguments = parser.parse_args()

    input_info = helper.make_tensor_value_info(
        "image", TensorProto.FLOAT, [1, 3, INPUT_HEIGHT, INPUT_WIDTH]
    )
    output_info = helper.make_tensor_value_info(
        "logits", TensorProto.FLOAT, [1, 1, INPUT_HEIGHT, INPUT_WIDTH]
    )
    node = helper.make_node("ReduceMean", ["image"], ["logits"], axes=[1], keepdims=1)
    graph = helper.make_graph([node], "container-contract-only", [input_info], [output_info])
    model = helper.make_model(
        graph,
        producer_name="nailsize-container-contract",
        opset_imports=[helper.make_operatorsetid("", 17)],
    )
    model.metadata_props.add(key="nailsize.model_version", value=arguments.version)
    arguments.destination.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, arguments.destination)


if __name__ == "__main__":
    main()
