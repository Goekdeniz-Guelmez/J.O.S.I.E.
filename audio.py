from typing import Tuple

from einops import rearrange

import torch
import torch.nn as nn

from args import ModelArgs
from utils import RMSNorm
from encoder_transformer import TemporalDepthEncoderTransformer
from decoder_transformer import TemporalDepthDecoderTransformer


class AudioQuantizer(nn.Module):
    """Quantizer with temporal, depth, and spectral codebooks"""
    def __init__(self, args: ModelArgs):
        super().__init__()
        self.args = args
        self.num_quantizers = args.encoder_audio_num_quantizers
        self.codebook_size = args.encoder_audio_codebook_size
        self.hidden_dim = args.encoder_audio_hidden_dim

        self.input_norm = RMSNorm(self.hidden_dim, eps=self.args.encoder_audio_rms_norm_eps)

        # Temporal codebooks - for sequence-level patterns
        self.temporal_codebooks = nn.ModuleList(
            [
                nn.Embedding(self.codebook_size, (self.hidden_dim // self.num_quantizers))
                for _ in range(self.num_quantizers)
            ]
        )
        self.temporal_output_norm = RMSNorm(self.hidden_dim, eps=self.args.encoder_audio_rms_norm_eps)

        # Depth codebooks - for feature-level patterns
        self.depth_codebooks = nn.ModuleList(
            [
                nn.Embedding(self.codebook_size, (self.hidden_dim // self.num_quantizers))
                for _ in range(self.num_quantizers)
            ]
        )
        self.depth_output_norm = RMSNorm(self.hidden_dim, eps=self.args.encoder_audio_rms_norm_eps)

    def quantize_temporial(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        B, T, D = x.shape

        x = rearrange(x, 'b t (q d) -> b t q d', q=self.num_quantizers)

        indices = []
        quantized = []

        for i, codebook in enumerate(self.temporal_codebooks):
            distances = torch.cdist(x[..., i, :], codebook.weight)
            idx = distances.argmin(dim=-1)
            indices.append(idx)
            quantized.append(codebook(idx))

        indices = torch.stack(indices, dim=-1)
        quantized = torch.cat(quantized, dim=-1)

        return quantized, indices
    
    def quantize_depth(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        B, T, D = x.shape

        x = rearrange(x, 'b t (q d) -> b t q d', q=self.num_quantizers)
        
        indices = []
        quantized = []
        
        for i, codebook in enumerate(self.depth_codebooks):
            distances = torch.cdist(x[..., i, :], codebook.weight)
            idx = distances.argmin(dim=-1)
            indices.append(idx)
            quantized.append(codebook(idx))
        
        indices = torch.stack(indices, dim=-1)
        quantized = torch.cat(quantized, dim=-1)
        
        return quantized, indices
    
    def forward(self, x: torch.Tensor, stream_type: str = 'temporal') -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Quantize input based on stream type
        stream_type: One of 'temporal', 'depth', or 'spectral'
        """
        x = self.input_norm(x)

        if stream_type == 'temporal':
            quantized, indices = self.quantize_temporial(x)
            return self.temporal_output_norm(quantized), indices
        
        elif stream_type == 'depth':
            quantized, indices = self.quantize_depth(x)
            return self.depth_output_norm(quantized), indices

        else:
            raise ValueError(f"Unknown stream type: {stream_type}")


class AudioEncoder(nn.Module):
    """Quantizer with temporal, depth, and spectral codebooks"""
    def __init__(self, args: ModelArgs):
        super().__init__()
        self.args = args

        self.quantizer = AudioQuantizer(args)

        self.temporial_transformer = TemporalDepthEncoderTransformer(args)
        self.depth_transformer = TemporalDepthEncoderTransformer(args)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        temporal_quantized, _ = self.quantizer(x)
        depth_quantized, _ = self.quantizer(x, 'depth')

        temporialed, _ = self.temporial_transformer(temporal_quantized)
        depthed, _ = self.depth_transformer(depth_quantized)

        discrete_audio_tokens = temporialed + depthed
        return discrete_audio_tokens



class AudioDecoder(nn.Module):
    """Quantizer with temporal, depth, and spectral codebooks"""
    def __init__(self, args: ModelArgs):
        super().__init__()
        self.args = args

        self.hidden_dim = args.encoder_audio_hidden_dim

        self.quantizer = AudioQuantizer(args)

        self.temporial_transformer = TemporalDepthDecoderTransformer(args)
        self.depth_transformer = TemporalDepthDecoderTransformer(args)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        temporal_quantized, _ = self.quantizer(x)
        depth_quantized, _ = self.quantizer(x, 'depth')

        temporialed, _ = self.temporial_transformer(temporal_quantized)
        depthed, _ = self.depth_transformer(depth_quantized)

        discrete_audio_tokens = temporialed + depthed
        return discrete_audio_tokens


class AudioEncoderDecoder(nn.Module):
    """Quantizer with temporal, depth, and spectral codebooks"""
    def __init__(self, args: ModelArgs):
        super().__init__()
        self.args = args

        self.hidden_dim = args.encoder_audio_hidden_dim

        self.encoder = AudioEncoder(args)
        self.decoder = AudioDecoder(args)
    
    def forward(self, x: torch.Tensor, style: str = 'encode') -> torch.Tensor:
        if style == 'encode':
            output = self.encoder(x)
        elif style == 'decode':
            output = self.decoder(x)
        else:
            return f'style wasnt found {style}'
        
        return output
    
    def encode(self, x: torch.Tensor) -> torch.Tensor:
        return self.encoder(x)
    
    def decode(self, x: torch.Tensor) -> torch.Tensor:
        return self.decoder(x)