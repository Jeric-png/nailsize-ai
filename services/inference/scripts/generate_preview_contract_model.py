import argparse
from pathlib import Path

import onnx
from onnx import TensorProto, helper

INPUT_WIDTH = 160
INPUT_HEIGHT = 224


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a synthetic model for non-measuring deployment previews"
    )
    parser.add_argument("destination", type=Path)
    arguments = parser.parse_args()

    input_info = helper.make_tensor_value_info(
        "image", TensorProto.FLOAT, [1, 3, INPUT_HEIGHT, INPUT_WIDTH]
    )
    output_info = helper.make_tensor_value_info(
        "logits", TensorProto.FLOAT, [1, 1, INPUT_HEIGHT, INPUT_WIDTH]
    )
    node = helper.make_node("ReduceMean", ["image"], ["logits"], axes=[1], keepdims=1)
    graph = helper.make_graph([node], "deployment-preview-only", [input_info], [output_info])
    model = helper.make_model(
        graph,
        producer_name="nailsize-deployment-preview",
        opset_imports=[helper.make_operatorsetid("", 17)],
    )
    model.metadata_props.add(key="nailsize.model_version", value="deployment-preview-only")
    arguments.destination.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, arguments.destination)


if __name__ == "__main__":
    main()
